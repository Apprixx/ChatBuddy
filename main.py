from wxauto import *
from datetime import date
import openai
import re
import time
import os
import json
import atexit
import sys

wx = WeChat()

# 全局
admin = []
VIP = []
default = []
user_info = {}
group_chat = []
groups_chat_info= {}
PREFIX = "" #群聊消息识别前缀
C_PREFIX = "/"#指令识别前缀
help = "help"
main_path = "C:/Users/Administrator/Projects/ChatBuddy"
roles_path = "C:/Users/Administrator/Projects/ChatBuddy/roles"
default_model = "DeepseekV3"
start_of_prompt = "如果和你说话的人没有提某些专业方面的问题,请相对简短地回答,不超过50个字,如果提了,请提供最专业且详细的回答"
MAX_TOKENS = 300



os.chdir(main_path)
print("切换后工作目录:", os.getcwd())

# 配置DeepSeek API
DEEPSEEK_API_KEY = ""
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


# 指令列表
admin_command_list = [
    f"移除(重启生效,格式:{C_PREFIX}移除,组名,用户名)",
    f"添加(重新加载生效,格式:{C_PREFIX}添加,组名,用户名)",
    f"群人设(获取此群的人设,格式:{C_PREFIX}群人设,群名称)",
    f"移除人设(移除对应人设,格式:{C_PREFIX}移除人设,人设名称)",
    f"加载群人设(加载此群的人设,格式:{C_PREFIX}加载群人设,群名称,人设名称)",
    f"设置好感度(设置某群的好感度.格式:{C_PREFIX}设置好感度,群名称,好感度)",
    "人设内容(获取完整人设内容)",
    "加载组(重新加载所有组)",
    "组信息(获取所有组的用户列表)",
    "保存(手动保存所有历史记录)",
]

VIP_command_list = [
    
]

default_command_list = [
    "菜单(展示此列表)",
    "帮助(提供指令语法帮助)",
    "重置(清空当前角色历史记录)",
    "存档信息(获取所有存档信息)",
    "角色列表(获取所有角色名称)",
    f"存档(格式:{C_PREFIX}存档,存档名称)",
    f"读档(格式:{C_PREFIX}读档,存档名称)",
    f"删除存档(格式:{C_PREFIX}删除存档,存档名称)",
    f"加载人设(格式:{C_PREFIX}加载人设,人设名称)",
    f"上传人设(格式:{C_PREFIX}上传人设,人设名称,是否匿名,是否公开,人设提示词)",
]

group_command_list = [
    "菜单(展示此列表)",
    "帮助(提供帮助)",
    "重置(清空历史记录)",
    "好感度(列出所有人的好感度)",
    "对话次数(返回总对话次数)"
]

retain_field = [
    "group_prompt",
    "help"
]

# 处理指令
def process_command(who, msg):
    content = msg.strip()
    if not content.startswith(C_PREFIX):
        print("匹配指令前缀失败")
        return False
    content = content[len(C_PREFIX):].strip()
    print(f"匹配指令前缀成功:\n{content}")
    if process_group_command(who, content):
        return True
    if process_admin_command(who, content):
        return True
    match content:
        case "菜单":
            menu = "指令列表:"
            for element in default_command_list+admin_command_list if who in admin else default_command_list:
                menu += f"\n{element}"
            wx.SendMsg(menu, who)
        case "帮助":
            wx.SendMsg(get_prompt(help), who)
        case "重置":
            init_user(who)
            wx.SendMsg("已清空历史记录", who)
        case "存档信息":
            send_saves_info(who)
        case "角色列表":
            send_role_list(who)   
        case content if content[:2] == "存档":
            save(who, content[3:])
        case content if content[:2] == "读档":
            load_save(who, content[3:])
        case content if content[:4] == "删除存档":
            remove_save(who, content[5:])
        case content if content[:4] == "加载人设":
            load_role(who, content[5:])
        case content if content[:4] == "上传人设":
            add_role(who, content[5:])
        case _:
            print(f"无效指令{content}")
            wx.SendMsg("未知指令,请查询菜单",who)
    return True


# 处理管理员指令
def process_admin_command(who, content):
    if who not in admin:
        return False
    print("匹配到admin")
    match content:
        case "加载组":
            wx.SendMsg("加载成功" if init_user_group() else "加载失败", who)
        case "组信息":
            wx.SendMsg(f"Admin:\n{admin}\nVIP:\n{VIP}\nDefault:\n{default}\nGroup_chat:\n{group_chat}", who)
        case "保存":
            wx.SendMsg("已保存" if save_all() else "保存失败",who)
        case content if content[:2] == "移除":
            parts = content[4:].split(",")
            wx.SendMsg(f"已移除{parts[1]}" if remove_from_group(parts[0],parts[1]) else "移除失败",who)
        case content if content[:2] == "添加":
            parts = content[3:].split(",")
            wx.SendMsg(f"已添加{parts[1]}" if add_to_group(parts[0],parts[1]) else "添加失败",who)
        case content if content[:4] == "移除人设":
            remove_role(content[5:])
        case content if content[:3] == "群人设":
            send_group_role(who, content[4:])
        case content if content[:5] == "加载群人设":
            load_group_role(who, content[6:])
        case content if content[:5] == "设置好感度":
            set_favorability(who, content[6:])
        case _:
            return False
    return True

def load_group_role(who, content):
    try:
        parts = content.split(",")
        print(parts[0])
        if parts[0] not in groups_chat_info:
            wx.SendMsg(f"无效组名{parts[0]}", who)
        with open("role_list.json","r",encoding='utf-8') as file:
            roles = json.load(file)
        if parts[1] in roles:
            init_one_group_chat(parts[0], parts[1])
            wx.SendMsg("成功加载人设", who)
        else:
            wx.SendMsg("加载失败,此名称不存在", who)
    except Exception as e:
        print(f"格式错误{e}")
        wx.SendMsg(f"格式错误{e}", who)


def process_group_command(who, content):
    if who not in group_chat:
        return False
    print("匹配到group_chat")
    match content:
        case "菜单":
            menu = "指令列表:"
            for element in group_command_list:
                menu += f"\n{element}"
            wx.SendMsg(menu, who)
        case "重置":
            init_one_group_chat(who, groups_chat_info[who]["角色"],False)
            wx.SendMsg("已清空历史记录", who)
        case "好感度":
            send_favorability(who)
        case "对话次数":
            send_conversation_count(who)
        case "帮助":
            wx.SendMsg(get_prompt(help), who)
        case _:
            wx.SendMsg("未知指令,请查询菜单",who)
    return True


def send_group_role(who, group):
    role = groups_chat_info.get(group).get("角色") 
    wx.SendMsg(f"当前人设:{role}" if role != None else "无效群名称", who)


# 初始化DeepSeek客户端
def init_deepseek_client():
    client = openai.OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL
    )
    return client

def process_private_chat_msg(who, content):
    user_info[who]["历史记录"].append({"role":"user","content":content})
    if len(user_info[who]["历史记录"]) > 11:
        user_info[who]["历史记录"].pop(1)
        user_info[who]["历史记录"].pop(1)
    reply = get_deepseek_response(user_info[who]["历史记录"])
    user_info[who]["历史记录"].append({"role":"assistant","content":reply})
    # user_info[who]["计数器"] = str(int(user_info[who]["计数器"]) + 2) 
    return reply

def process_group_chat_msg(who, content, sender):
    if sender not in groups_chat_info[who]["群成员"]:
        groups_chat_info[who]["群成员"][sender] = "0"
    groups_chat_info[who]["历史记录"].append({"role":"user","content":f"此时说话的人:{sender}\n他说的话:{content}"})
    if len(groups_chat_info[who]["历史记录"]) > 15:
        groups_chat_info[who]["历史记录"].pop(1)
        groups_chat_info[who]["历史记录"].pop(1)
    prompt = get_prompt(groups_chat_info[who]["角色"]) + get_prompt("group_prompt")
    groups_chat_info[who]["历史记录"][0]["content"] = start_of_prompt + prompt + str(groups_chat_info[who]["群成员"])
    reply = get_deepseek_response(groups_chat_info[who]["历史记录"])
    print(reply)
    groups_chat_info[who]["历史记录"].append({"role":"assistant","content":reply})
    print(groups_chat_info[who]["历史记录"])
    # groups_chat_info[who]["计数器"] = str(int(groups_chat_info[who]["计数器"]) + 1)
    try:
        position = reply.rfind("(")
        if position != -1:
            score = int(reply[position+1:-1])
        if abs(int(groups_chat_info[who]["群成员"][sender])-score) <= 3 and score >= -100 and score <= 100:
            groups_chat_info[who]["群成员"][sender] = str(score)
        else:
            print("超出3分范围或超出上下限")
    except Exception as e:
        print(f"截取好感度失败:{e}")
    return reply



def get_deepseek_response(chat_history):
    try:
        client = init_deepseek_client()
        print("Waiting response form deepseek......")
        if not client:
            print("DeepSeek客户端初始化失败,请检查API密钥和网络")
            return "DeepSeek客户端初始化失败,请检查API密钥和网络"
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=chat_history,
            max_tokens=MAX_TOKENS,
            stream=False
        )
        reply = response.choices[0].message.content.strip()
        print("Response has been received")
        return reply
    except Exception as e:
        print(f"DeepSeek API unexpected error: {e}")
        return(f"DeepSeek API unexpected error: {e}")


def set_favorability(who, content):
    try:
        parts = content.split(",")
        if abs(int(parts[1])) <= 100:
            groups_chat_info[parts[0]]["群成员"][who] = parts[1]
            wx.SendMsg(f"设置成功:{parts[1]}", who)
    except Exception as e:
        wx.SendMsg(f"更改失败:{e}", who)


# 添加name到group组,返回bool
def add_to_group(group, name):
    with open("user_groups.json","r",encoding='utf-8') as file:
        groups = json.load(file)
    if group in groups and name not in groups[group]:
        groups[group].append(name)
        with open("user_groups.json","w",encoding='utf-8') as file:
            json.dump(groups,file,ensure_ascii=False,indent=4)
        return True
    return False
    
# 从group组移除name,返回bool 
def remove_from_group(group, name):
    with open("user_groups.json","r",encoding='utf-8') as file:
        groups = json.load(file)
    if group in groups and name in groups[group]:
        groups[group].pop(name)
        with open("user_groups.json","w",encoding='utf-8') as file:
            json.dump(groups,file,ensure_ascii=False,indent=4)
        return True
    return False

# 根据前缀提取内容
def extract_prefix_content(who, message):
    content = message.strip()
    if content.startswith(PREFIX):
        content_after_prefix = content[len(PREFIX):].strip()
        print(f"匹配前缀({PREFIX})成功:\n{content_after_prefix}")
        return content_after_prefix if content_after_prefix else "在吗"
    elif who in default+VIP+admin:
        return message
    else:
        print(f"匹配前缀({PREFIX})失败,忽略消息")
        return None

# 上传人设(格式:{C_PREFIX}上传人设,人设名称,是否匿名,是否公开,人设提示词)
def add_role(who, content):
    try:
        parts = content.split(",")
        role_name = parts[0].strip()
        is_anonymous = parts[1].strip()
        is_public = parts[2].strip()
        prompt = parts[3].strip()
        print(role_name)
        if role_name == "" or role_name in retain_field or len(role_name) >= 16:
            wx.SendMsg("不合法的名称",who)
            return None
        if not (is_anonymous == "是" or is_anonymous == "否"):
            wx.SendMsg("是否匿名处应为:(是/否)", who)
            return None
        if not (is_public == "是" or is_public == "否"):
            wx.SendMsg("是否公开处应为:(是/否)", who)
            return None
        with open("role_list.json","r",encoding='utf-8') as file:
            roles = json.load(file)
        with open("role_list.json","w",encoding='utf-8') as file:
            if role_name not in roles:
                roles[role_name] = {"上传者":who, "是否匿名":is_anonymous, "是否公开":is_public, "调用次数":"0", "上传日期":str(date.today())}
                json.dump(roles,file,ensure_ascii=False,indent=4)
                wx.SendMsg(f"成功添加:{role_name}", who)
            else:
                wx.SendMsg(f"此角色已存在:{role_name}", who)
        os.chdir(roles_path)
        with open(f"{role_name}.txt", "w", encoding="utf-8") as file:
            file.write(prompt)
        os.chdir(main_path)
        return True
    except IndexError:
        wx.SendMsg("上传失败:格式错误")
    except Exception as e:
        wx.SendMsg(f"上传失败:{e}", who) 

def send_role_list(who):
    with open("role_list.json","r",encoding='utf-8') as file:
        roles = json.load(file)
    print(f"roles:{roles}")
    public_roles = "公开角色列表:"
    private_roles = "私有角色列表:"
    private_list_is_empty = True
    for role in roles:
        if roles[role]["是否公开"] == "是":
            public_roles += f"\n名称:{role},上传者:" + (roles[role]["上传者"] if roles[role]["是否匿名"] == "否" else "佚名") + f",上传日期:{roles[role]["上传日期"]}"
        else:
            if roles[role]["上传者"] == who:
                private_roles += f"\n名称:{role},上传者:{who},上传日期:{roles[role]["上传日期"]}"
                private_list_is_empty = False
    wx.SendMsg(public_roles+"\n"+(private_roles + "\n这里什么也没有" if private_list_is_empty else private_roles), who)


def load_role(who, role_name):
    with open("role_list.json","r",encoding='utf-8') as file:
        roles = json.load(file)
    if role_name in roles:
        init_user(who, role_name)
        wx.SendMsg("成功加载人设", who)
    else:
        wx.SendMsg("加载失败,此名称不存在", who)

def remove_role(who, role_name):
    wx.SendMsg("此函数还没写完呢 happy lazy~",who)
    
# 存档
def save(who, name):
    if name:
        with open("saves.json","r",encoding='utf-8') as file:
            saves = json.load(file)
        current = user_info[who]
        if len(saves[who]) >= 3:
            wx.SendMsg(f"当前数量({len(saves[who])})达上限,请删除一个后重试", who)
        elif name in list(saves[who].keys()):
            wx.SendMsg(f"此名称已存在({name}),存档日期:{saves[who][name]["存档日期"]},请更改名称后重试", who)
        else:
            saves[who][name] = current
            saves[who][name]["存档日期"] = str(date.today())
            print(saves)
            with open("saves.json","w",encoding='utf-8') as file:
                json.dump(saves,file,ensure_ascii=False,indent=4)
            wx.SendMsg(f"已存档:{name},当前数量:{len(saves[who])}",who)
    else:
        wx.SendMsg(f"不合法的名称:{name}",who)

# 读档
def load_save(who, name):
    with open("saves.json","r",encoding='utf-8') as file:
        saves = json.load(file)
    if saves[who].get(name, None) == None:
        wx.SendMsg(f"此存档不存在:{name}",who)
    else:
        user_info[who] = saves[who][name]
        user_info[who].pop("存档日期")
        wx.SendMsg(f"已读档:{name},当前数量:{len(saves[who])}",who)

# 删除存档
def remove_save(who, name):
    with open("saves.json","r",encoding='utf-8') as file:
        saves = json.load(file)
    if saves[who].get(name, None) == None:
        wx.SendMsg(f"此存档不存在:{name}",who)     
    else:
        saves[who].pop(name)
        with open("saves.json","w",encoding='utf-8') as file:
            json.dump(saves,file,ensure_ascii=False,indent=4)
        wx.SendMsg(f"已删除:{name},当前数量:{len(saves[who])}",who)

# 向who发送存档信息
def send_saves_info(who):
    with open("saves.json","r",encoding='utf-8') as file:
        saves = json.load(file)
    info = "(存档名,角色名,创建日期)"
    for save in saves[who]:
        info = info + f"\n({save},{saves[who][save]["角色"]},{saves[who][save]["存档日期"]})"
    info = info + "\n" + "合计: " + str(len(saves[who]))
    wx.SendMsg(info,who)

# 通过file_name读取提示词
def get_prompt(file_name):
    os.chdir(roles_path)
    try:
        with open(f"{file_name}.txt", 'r', encoding='utf-8') as file:
            content = file.read().strip()
        print(f"从{file_name}.txt读取内容")
        os.chdir(main_path)
        return content
    except Exception as e:
        print(f"读取文件失败: {e}")
        os.chdir(main_path)
        return "读取失败"
    
# 将全局user_info存到json
def save_all():
    try:
        with open("user_info.json","w",encoding='utf-8') as file:
            json.dump(user_info,file,ensure_ascii=False,indent=4)    
        with open("groups_chat_info.json","w",encoding='utf-8') as file:
            json.dump(groups_chat_info,file,ensure_ascii=False,indent=4)    
        return True
    except Exception as e:
        print(f"保存失败:{e}")
        return False

# 单独初始化一个用户,并更新到全局user_info  
def init_user(who, role_name=default_model):
    global user_info
    user_info[who] = {
        "角色":role_name,
        "计数器":"0",
        "核心记忆":"",
        "历史记录":[
            {
                "role":"system",
                "content":start_of_prompt+get_prompt(role_name)
            }
        ]
    }
    print(f"初始化:{who},角色:{role_name}")

# 初始化新用户信息:并从json加载user_info
def init_user_info():
    global user_info
    with open("user_info.json","r",encoding='utf-8') as file:
        user_info = json.load(file)    
    for user in default+VIP+admin:
        if user not in user_info:
            init_user(user)
    with open("user_info.json","w",encoding='utf-8') as file:
        json.dump(user_info,file,ensure_ascii=False,indent=4)

# 从user_info.json加载全局user_info
def load_user_info(): 
    global user_info
    with open("user_info.json","r",encoding='utf-8') as file:
        user_info = json.load(file)

def init_save():
    with open("saves.json","r",encoding='utf-8') as file:
        saves = json.load(file)
    for user in user_info:
        if user not in saves:
            saves[user] = {} 
    with open("saves.json","w",encoding='utf-8') as file:
        json.dump(saves,file,ensure_ascii=False,indent=4)

# 初始化所有组
def init_user_group():
    try:
        with open("user_groups.json","r",encoding='utf-8') as file:
            groups = json.load(file)
        global admin,VIP,default,group_chat
        admin = groups["Admin"]
        VIP = groups["VIP"]
        default = groups["Default"]
        group_chat = groups["Groups"]
        init_user_info()
        init_group_chat()
        add_listen_chats()
        print("初始化group成功")
        return "初始化group成功"
    except Exception as e:
        print(f"初始化失败:{e}")
        return f"初始化失败:{e}"

def increase_role_count(who, is_group_chat):
    with open("role_list.json","r",encoding='utf-8') as file:
        roles = json.load(file)
    with open("role_list.json","w",encoding='utf-8') as file:
        if is_group_chat:
            roles[groups_chat_info[who]["角色"]]["调用次数"] = str(int(roles[groups_chat_info[who]["角色"]]["调用次数"])+1)
        else:
            roles[user_info[who]["角色"]]["调用次数"] = str(int(roles[user_info[who]["角色"]]["调用次数"])+1)
        json.dump(roles,file,ensure_ascii=False,indent=4)

def send_conversation_count(who):
    with open("role_list.json","r",encoding='utf-8') as file:
        roles = json.load(file)
    try:
        wx.SendMsg(roles[groups_chat_info[who]["角色"]]["调用次数"],who)
    except Exception as e:
        wx.SendMsg("获取次数失败",who)

def init_group_chat():
    global groups_chat_info 
    with open("groups_chat_info.json","r",encoding='utf-8') as file:
        groups_chat_info = json.load(file)
    for group in group_chat:
        if group not in groups_chat_info:
            init_one_group_chat(group)
    with open("groups_chat_info.json","w",encoding='utf-8') as file:
        json.dump(groups_chat_info,file,ensure_ascii=False,indent=4)

def init_one_group_chat(group,role_name=default_model,is_reset = True):
    global groups_chat_info
    if is_reset:
        groups_chat_info[group] = {
                "角色":role_name,
                "计数器":"0",
                "核心记忆":"",
                "历史记录":[
                    {
                        "role":"system",
                        "content":""
                    }
                ],
                "群成员":{

                }
            }
    else:
        groups_chat_info[group]["历史记录"] = []
        groups_chat_info[group]["核心记忆"] = ""
    print(f"初始化:{group},角色:{role_name}")
    
def send_favorability(who):
    favorability_str = "好感度列表:"
    for element in groups_chat_info[who]["群成员"]:
        favorability_str += "\n" + element + ":" + groups_chat_info[who]["群成员"][element]
    wx.SendMsg(favorability_str, who)

# 添加监听列表
def add_listen_chats():
    for who in admin+VIP+default+group_chat:
        try:
            wx.AddListenChat(who=who)
            print(f"添加监听:{who}")
        except Exception as e:
            print(f"添加失败:{e}")

def monitor_and_process():
    while True:
        msgs = wx.GetListenMessage()
        for chat in msgs:
            one_msg = msgs.get(chat)
            for msg in one_msg:
                print(f"msg:\n{msg}")
                if msg.type == "friend":
                    content = msg.content
                    who = chat.who
                    content = extract_prefix_content(who, content)
                    if content != None:
                        if not process_command(who, content):
                            if who in group_chat:
                                wx.SendMsg(process_group_chat_msg(who, content, msg.sender), who)
                                increase_role_count(who, True)
                            else:
                                wx.SendMsg(process_private_chat_msg(who, content), who)
                                increase_role_count(who, False)
        time.sleep(1)

def run():
    init_user_group()
    init_save()
    monitor_and_process()

run()
