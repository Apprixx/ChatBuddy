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
    # 去除消息前后的空格
    content = msg.strip()

    # 判断消息是否以指令前缀（C_PREFIX）开头，例如“/”
    if not content.startswith(C_PREFIX):
        print("匹配指令前缀失败")
        return False  # 如果没有匹配到前缀，返回 False 表示不是指令

    # 去掉前缀部分，只保留实际指令内容
    content = content[len(C_PREFIX):].strip()
    print(f"匹配指令前缀成功:\n{content}")

    # 先尝试处理群聊专用指令（例如 /群公告、/禁言 等）
    if process_group_command(who, content):
        return True  # 若该函数成功处理，则结束流程

    # 再尝试处理管理员专用指令（例如 /重启、/封禁 等）
    if process_admin_command(who, content):
        return True  # 若匹配成功则返回 True，不再继续往下匹配

    # 使用结构化匹配（Python 3.10+ 的 match-case）来处理普通用户指令
    match content:
        # 查看菜单（指令列表）
        case "菜单":
            menu = "指令列表:"
            # 如果用户是管理员，显示管理员+默认指令；否则只显示默认指令
            for element in default_command_list + admin_command_list if who in admin else default_command_list:
                menu += f"\n{element}"
            wx.SendMsg(menu, who)  # 发送指令菜单到聊天窗口

        # 查看帮助信息
        case "帮助":
            wx.SendMsg(get_prompt(help), who)

        # 清除用户的历史记录（如上下文、会话状态等）
        case "重置":
            init_user(who)
            wx.SendMsg("已清空历史记录", who)

        # 查询当前用户的存档信息（如游戏或AI对话存档）
        case "存档信息":
            send_saves_info(who)

        # 查看可加载的人物设定列表
        case "角色列表":
            send_role_list(who)

        # 存档相关操作：保存当前状态到指定名字的存档
        case content if content[:2] == "存档":
            save(who, content[3:])  # 取出“存档xxx”中的存档名并保存

        # 从指定存档中读取状态
        case content if content[:2] == "读档":
            load_save(who, content[3:])

        # 删除指定存档
        case content if content[:4] == "删除存档":
            remove_save(who, content[5:])

        # 从文件或数据库加载人物设定（如角色背景、人设等）
        case content if content[:4] == "加载人设":
            load_role(who, content[5:])

        # 上传自定义人设
        case content if content[:4] == "上传人设":
            add_role(who, content[5:])

        # 未匹配的指令处理
        case _:
            print(f"无效指令{content}")
            wx.SendMsg("未知指令,请查询菜单", who)

    # 若指令被正常处理，返回 True
    return True


# 处理管理员指令
def process_admin_command(who, content):
    # 判断发送者是否在管理员列表中
    # 如果不是管理员，则直接返回 False，表示该指令不是管理员指令
    if who not in admin:
        return False

    print("匹配到admin")  # 调试输出：确认当前执行的是管理员指令

    # 使用结构化匹配，根据指令内容执行不同的管理员操作
    match content:
        # 指令：加载组
        # 功能：重新初始化用户分组（Admin、VIP、Default等）
        case "加载组":
            wx.SendMsg("加载成功" if init_user_group() else "加载失败", who)

        # 指令：组信息
        # 功能：查看当前分组的成员信息
        case "组信息":
            wx.SendMsg(
                f"Admin:\n{admin}\nVIP:\n{VIP}\nDefault:\n{default}\nGroup_chat:\n{group_chat}",
                who
            )

        # 指令：保存
        # 功能：保存当前所有配置（如用户信息、分组、角色、存档等）
        case "保存":
            wx.SendMsg("已保存" if save_all() else "保存失败", who)

        # 指令示例：移除组别成员，如 “移除VIP,张三”
        # 功能：将某个用户从指定分组中移除
        case content if content[:2] == "移除":
            parts = content[4:].split(",")  # 提取格式 “移除组名,成员名” 中的参数
            # parts[0] = 组名，parts[1] = 成员名
            wx.SendMsg(
                f"已移除{parts[1]}" if remove_from_group(parts[0], parts[1]) else "移除失败",
                who
            )

        # 指令示例：添加组别成员，如 “添加VIP,张三”
        # 功能：将某个用户添加到指定分组
        case content if content[:2] == "添加":
            parts = content[3:].split(",")  # 提取 “添加组名,成员名”
            wx.SendMsg(
                f"已添加{parts[1]}" if add_to_group(parts[0], parts[1]) else "添加失败",
                who
            )

        # 指令示例：移除人设XXX
        # 功能：删除指定角色的人设（通常是角色配置文件或数据库条目）
        case content if content[:4] == "移除人设":
            remove_role(content[5:])

        # 指令示例：群人设XXX
        # 功能：发送指定群聊的人设信息给管理员查看
        case content if content[:3] == "群人设":
            send_group_role(who, content[4:])

        # 指令示例：加载群人设XXX
        # 功能：从群聊中加载一组角色设定（可能对应特定主题/场景）
        case content if content[:5] == "加载群人设":
            load_group_role(who, content[6:])

        # 指令示例：设置好感度XXX
        # 功能：为某个角色或用户调整“好感度”参数（可能用于剧情或交互系统）
        case content if content[:5] == "设置好感度":
            set_favorability(who, content[6:])

        # 未匹配任何已知管理员指令 → 返回 False，让上层函数继续判断
        case _:
            return False

    # 若成功匹配并执行了任意一条管理员指令，返回 True
    return True


def load_group_role(who, content):
    try:
        # 将指令内容按逗号分隔，例如：
        # 指令示例：「加载群人设组名,人设名」
        # parts[0] = 群组名，parts[1] = 人设名
        parts = content.split(",")
        print(parts[0])  # 调试输出：打印目标群组名

        # 检查群组名是否存在于系统已记录的群聊信息中
        if parts[0] not in groups_chat_info:
            wx.SendMsg(f"无效组名{parts[0]}", who)
            # 注意：这里没有 return，意味着即使群组无效仍会继续执行后续代码
            # 若希望严格校验，可以在这里加上 `return` 以提前中断

        # 打开存放所有角色人设信息的 JSON 文件
        with open("role_list.json", "r", encoding='utf-8') as file:
            roles = json.load(file)  # 加载 JSON → Python 字典对象

        # 检查给定人设名是否存在
        if parts[1] in roles:
            # 初始化该群组的人设信息（绑定群组与对应角色）
            init_one_group_chat(parts[0], parts[1])
            wx.SendMsg("成功加载人设", who)
        else:
            # 若角色名不存在于角色列表中，返回失败提示
            wx.SendMsg("加载失败,此名称不存在", who)

    # 捕获所有异常（例如分隔符错误、文件不存在、索引越界等）
    except Exception as e:
        print(f"格式错误{e}")
        wx.SendMsg(f"格式错误{e}", who)

def process_group_command(who, content):
    # 判断当前发送者是否属于群聊用户（而非普通个人或管理员）
    # 若不在 group_chat 列表中，说明该指令不是群聊指令
    if who not in group_chat:
        return False

    print("匹配到group_chat")  # 调试输出：确认匹配到了群聊指令

    # 使用结构化匹配（match-case）匹配不同群聊指令
    match content:
        # 群聊菜单指令
        # 功能：列出所有群聊可用的指令（group_command_list）
        case "菜单":
            menu = "指令列表:"
            for element in group_command_list:
                menu += f"\n{element}"
            wx.SendMsg(menu, who)  # 将菜单内容发送回群聊

        # 重置群聊对话
        # 功能：清空该群聊的历史记录，但保留原绑定的角色设定
        case "重置":
            # 调用初始化函数，传入：
            #   who → 群聊标识
            #   groups_chat_info[who]["角色"] → 当前群聊绑定的角色
            #   False → 表示非首次初始化（不重新创建结构，只清空记录）
            init_one_group_chat(who, groups_chat_info[who]["角色"], False)
            wx.SendMsg("已清空历史记录", who)

        # 查看群聊的好感度
        # 功能：向群聊发送当前角色与群成员的好感度信息
        case "好感度":
            send_favorability(who)

        # 查看对话次数
        # 功能：统计并发送群聊的总对话次数或交互次数
        case "对话次数":
            send_conversation_count(who)

        # 群聊帮助
        # 功能：显示帮助提示文本（一般解释各指令功能）
        case "帮助":
            wx.SendMsg(get_prompt(help), who)

        # 未匹配的情况
        # 功能：提示用户输入的指令无效或不存在
        case _:
            wx.SendMsg("未知指令,请查询菜单", who)

    # 群聊指令被成功识别和处理，返回 True
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
    # 将用户的消息添加到其历史记录中
    # 数据结构示例：
    # user_info[who]["历史记录"] = [
    #     {"role": "user", "content": "你好"},
    #     {"role": "assistant", "content": "你好，有什么可以帮你？"}
    # ]
    user_info[who]["历史记录"].append({"role": "user", "content": content})

    # 限制历史记录长度，防止消息积累过多导致性能下降或上下文混乱
    # 这里最大保存 11 条（用户+AI交替），若超过则删除第二和第三条（保留最早一条开场上下文）
    if len(user_info[who]["历史记录"]) > 11:
        user_info[who]["历史记录"].pop(1)
        user_info[who]["历史记录"].pop(1)

    # 调用 AI 模型接口（如 DeepSeek、GPT 等），生成回复
    # 参数是整个历史对话上下文（包括用户与AI的历史发言）
    reply = get_deepseek_response(user_info[who]["历史记录"])

    # 将 AI 的回复也加入历史记录中，以便下一次对话能保持上下文
    user_info[who]["历史记录"].append({"role": "assistant", "content": reply})

    # 原本可能用于统计对话次数或轮次，这里被注释掉了
    # user_info[who]["计数器"] = str(int(user_info[who]["计数器"]) + 2)

    # 返回生成的回复文本，供外部函数（例如 wx.SendMsg）发送
    return reply


def process_group_chat_msg(who, content, sender):
    # ---------------------- 基础信息维护 ----------------------
    # 检查说话者是否在该群聊的成员列表中
    # 如果不是（第一次发言），则初始化该成员的好感度为 "0"
    if sender not in groups_chat_info[who]["群成员"]:
        groups_chat_info[who]["群成员"][sender] = "0"

    # 将当前消息添加进群聊的历史记录中
    # 格式化方式模拟「群聊上下文」提示，帮助 AI 判断是谁说的话
    groups_chat_info[who]["历史记录"].append({
        "role": "user",
        "content": f"此时说话的人:{sender}\n他说的话:{content}"
    })

    # ---------------------- 历史记录管理 ----------------------
    # 限制历史记录长度，避免上下文过长导致生成延迟或溢出
    # 若超过 15 条（约 7~8 轮对话），则删除第二、第三条记录
    # 这样能保留最初的系统 prompt 和最近的上下文
    if len(groups_chat_info[who]["历史记录"]) > 15:
        groups_chat_info[who]["历史记录"].pop(1)
        groups_chat_info[who]["历史记录"].pop(1)

    # ---------------------- prompt 拼接 ----------------------
    # 获取角色专属提示词 + 群聊专属提示词
    # 用于为 AI 提供角色背景和群聊行为规则
    prompt = get_prompt(groups_chat_info[who]["角色"]) + get_prompt("group_prompt")

    # 将 prompt 和群成员状态写入历史记录的第一条（系统消息）
    # start_of_prompt 通常为一个系统级提示头，例如 "你是一个群聊AI助手："
    groups_chat_info[who]["历史记录"][0]["content"] = (
        start_of_prompt + prompt + str(groups_chat_info[who]["群成员"])
    )

    # ---------------------- 调用 AI 模型生成回复 ----------------------
    reply = get_deepseek_response(groups_chat_info[who]["历史记录"])
    print(reply)  # 调试输出：打印模型回复内容

    # 将 AI 回复也添加入历史记录，便于维持对话上下文
    groups_chat_info[who]["历史记录"].append({
        "role": "assistant",
        "content": reply
    })

    print(groups_chat_info[who]["历史记录"])  # 调试输出：查看更新后的对话记录

    # 可选统计功能（被注释掉）
    # groups_chat_info[who]["计数器"] = str(int(groups_chat_info[who]["计数器"]) + 1)

    # ---------------------- 自动提取好感度机制 ----------------------
    try:
        # 查找回复中的最后一个括号 "("，假设AI输出形如：
        # “谢谢你的帮助！(+3)” 或 “有点失望。(-2)”
        position = reply.rfind("(")
        if position != -1:
            score = int(reply[position + 1 : -1])  # 提取括号内的整数部分

        # 若分数与原有好感度差值 ≤ 3 且在 -100~100 范围内，则更新好感度
        if abs(int(groups_chat_info[who]["群成员"][sender]) - score) <= 3 and -100 <= score <= 100:
            groups_chat_info[who]["群成员"][sender] = str(score)
        else:
            print("超出3分范围或超出上下限")

    # 捕获异常（常见如 AI 没返回括号格式、字符串转 int 失败等）
    except Exception as e:
        print(f"截取好感度失败:{e}")

    # 返回 AI 回复文本，由上层函数发送给群聊
    return reply




def get_deepseek_response(chat_history):
    try:
        # 初始化 DeepSeek 客户端
        client = init_deepseek_client()
        print("Waiting response form deepseek......")
        
        # 如果客户端初始化失败，打印错误并返回提示信息
        if not client:
            print("DeepSeek客户端初始化失败,请检查API密钥和网络")
            return "DeepSeek客户端初始化失败,请检查API密钥和网络"
        
        # 调用 DeepSeek API 生成对话回复
        response = client.chat.completions.create(
            model="deepseek-chat",   # 使用的模型名称
            messages=chat_history,   # 传入聊天历史记录
            max_tokens=MAX_TOKENS,   # 最大回复长度
            stream=False             # 不使用流式输出
        )
        
        # 获取回复内容并去掉首尾空格
        reply = response.choices[0].message.content.strip()
        print("Response has been received")
        return reply
    
    except Exception as e:
        # 捕获异常，打印并返回错误信息
        print(f"DeepSeek API unexpected error: {e}")
        return(f"DeepSeek API unexpected error: {e}")



def set_favorability(who, content):
    try:
        # 将传入内容按逗号分割，通常格式为 "群名,分数"
        parts = content.split(",")

        # 检查分数是否在允许范围内（-100 到 100）
        if abs(int(parts[1])) <= 100:
            # 更新指定群里该用户的好感度
            groups_chat_info[parts[0]]["群成员"][who] = parts[1]
            wx.SendMsg(f"设置成功:{parts[1]}", who)
    except Exception as e:
        # 捕获异常并提示修改失败
        wx.SendMsg(f"更改失败:{e}", who)



# 添加name到group组,返回bool
def add_to_group(group, name):
    # 打开并读取用户分组信息的 JSON 文件
    with open("user_groups.json","r",encoding='utf-8') as file:
        groups = json.load(file)
    
    # 如果指定的组存在，并且用户不在组里
    if group in groups and name not in groups[group]:
        # 将用户添加到该组
        groups[group].append(name)
        
        # 将更新后的分组信息写回文件
        with open("user_groups.json","w",encoding='utf-8') as file:
            json.dump(groups,file,ensure_ascii=False,indent=4)
        return True  # 添加成功
    
    return False  # 添加失败（组不存在或用户已在组里）

    

# 从group组移除name,返回bool 
def remove_from_group(group, name):
# 从 group 组移除指定成员 name，返回操作是否成功
def remove_from_group(group, name):
    # 读取用户分组信息 JSON 文件
    with open("user_groups.json","r",encoding='utf-8') as file:
        groups = json.load(file)
    
    # 如果组存在并且成员在组里
    if group in groups and name in groups[group]:
        # 注意：pop() 默认使用索引，这里应使用 remove() 来移除指定成员
        groups[group].remove(name)
        
        # 将更新后的分组信息写回文件
        with open("user_groups.json","w",encoding='utf-8') as file:
            json.dump(groups,file,ensure_ascii=False,indent=4)
        return True  # 移除成功
    
    return False  # 移除失败（组不存在或成员不在组中）


# 根据前缀提取内容
def extract_prefix_content(who, message):
    # 去掉消息前后的空格
    content = message.strip()
    
    # 如果消息以指定前缀开头
    if content.startswith(PREFIX):
        # 提取前缀后的内容并去掉空格
        content_after_prefix = content[len(PREFIX):].strip()
        print(f"匹配前缀({PREFIX})成功:\n{content_after_prefix}")
        # 如果内容不为空返回内容，否则默认返回“在吗”
        return content_after_prefix if content_after_prefix else "在吗"
    
    # 如果发送者是默认用户、VIP或管理员，直接返回原消息
    elif who in default+VIP+admin:
        return message
    
    # 对其他用户消息不处理，返回None
    else:
        print(f"匹配前缀({PREFIX})失败,忽略消息")
        return None


# 上传人设(格式:{C_PREFIX}上传人设,人设名称,是否匿名,是否公开,人设提示词)
def add_role(who, content):
    try:
        # 将用户输入的内容按逗号分割
        # 期望格式为：角色名,是否匿名,是否公开,提示词
        parts = content.split(",")
        role_name = parts[0].strip()  # 角色名称
        is_anonymous = parts[1].strip()  # 是否匿名（是/否）
        is_public = parts[2].strip()  # 是否公开（是/否）
        prompt = parts[3].strip()  # 角色的提示词内容

        print(role_name)

        # 检查角色名是否合法：不能为空、不能为保留字段、长度不能超过16
        if role_name == "" or role_name in retain_field or len(role_name) >= 16:
            wx.SendMsg("不合法的名称", who)
            return None
        
        # 检查“是否匿名”参数是否为“是”或“否”
        if not (is_anonymous == "是" or is_anonymous == "否"):
            wx.SendMsg("是否匿名处应为:(是/否)", who)
            return None
        
        # 检查“是否公开”参数是否为“是”或“否”
        if not (is_public == "是" or is_public == "否"):
            wx.SendMsg("是否公开处应为:(是/否)", who)
            return None

        # 打开角色列表JSON文件，读取现有角色信息
        with open("role_list.json","r",encoding='utf-8') as file:
            roles = json.load(file)

        # 写入新的角色信息
        with open("role_list.json","w",encoding='utf-8') as file:
            if role_name not in roles:
                # 角色不存在时添加新角色
                roles[role_name] = {
                    "上传者": who, 
                    "是否匿名": is_anonymous, 
                    "是否公开": is_public, 
                    "调用次数": "0", 
                    "上传日期": str(date.today())
                }
                json.dump(roles,file,ensure_ascii=False,indent=4)
                wx.SendMsg(f"成功添加:{role_name}", who)
            else:
                # 若角色名已存在则提示
                wx.SendMsg(f"此角色已存在:{role_name}", who)

        # 进入存放角色文件的目录
        os.chdir(roles_path)
        # 创建一个以角色名命名的txt文件，并写入prompt内容
        with open(f"{role_name}.txt", "w", encoding="utf-8") as file:
            file.write(prompt)
        # 写入完后回到主路径
        os.chdir(main_path)

        return True

    # 如果用户输入格式不正确（例如逗号数量不够）
    except IndexError:
        wx.SendMsg("上传失败:格式错误")

    # 捕获其他异常，打印错误信息
    except Exception as e:
        wx.SendMsg(f"上传失败:{e}", who)


def send_role_list(who):
    # 打开角色列表 JSON 文件并读取内容
    with open("role_list.json","r",encoding='utf-8') as file:
        roles = json.load(file)
    
    # 打印调试信息，查看当前读取的角色数据
    print(f"roles:{roles}")

    # 初始化公开角色列表和私有角色列表字符串
    public_roles = "公开角色列表:"
    private_roles = "私有角色列表:"
    private_list_is_empty = True  # 用于判断私有列表是否为空

    # 遍历所有角色
    for role in roles:
        # 如果角色是公开的
        if roles[role]["是否公开"] == "是":
            # 显示角色名称、上传者（匿名则显示“佚名”）、上传日期
            public_roles += f"\n名称:{role},上传者:" + \
                            (roles[role]["上传者"] if roles[role]["是否匿名"] == "否" else "佚名") + \
                            f",上传日期:{roles[role]['上传日期']}"
        else:
            # 如果角色是私有的且上传者是当前用户
            if roles[role]["上传者"] == who:
                private_roles += f"\n名称:{role},上传者:{who},上传日期:{roles[role]['上传日期']}"
                private_list_is_empty = False  # 标记私有列表非空

    # 发送消息给用户：公开列表 + 私有列表（如果私有列表为空则显示“这里什么也没有”）
    wx.SendMsg(
        public_roles + "\n" + 
        (private_roles + "\n这里什么也没有" if private_list_is_empty else private_roles),
        who
    )



def load_role(who, role_name):
    # 打开角色列表文件并读取所有角色信息
    with open("role_list.json","r",encoding='utf-8') as file:
        roles = json.load(file)
    
    # 如果指定角色存在，则为该用户初始化该角色
    if role_name in roles:
        init_user(who, role_name)  # 初始化用户角色及历史记录
        wx.SendMsg("成功加载人设", who)  # 发送成功提示
    else:
        # 如果角色不存在，则发送失败提示
        wx.SendMsg("加载失败,此名称不存在", who)


def remove_role(who, role_name):
    wx.SendMsg("此函数还没写完呢 happy lazy~",who)
    
# 存档
def save(who, name):
    # 检查存档名称是否存在
    if name:
        # 打开存档 JSON 文件并读取内容
        with open("saves.json","r",encoding='utf-8') as file:
            saves = json.load(file)
        
        # 获取当前用户的信息
        current = user_info[who]
        
        # 检查该用户已有存档数量是否达到上限（3 个）
        if len(saves[who]) >= 3:
            wx.SendMsg(f"当前数量({len(saves[who])})达上限,请删除一个后重试", who)
        
        # 检查存档名称是否已存在
        elif name in list(saves[who].keys()):
            wx.SendMsg(f"此名称已存在({name}),存档日期:{saves[who][name]['存档日期']},请更改名称后重试", who)
        
        # 如果名称合法且数量未达上限，则保存当前用户信息
        else:
            saves[who][name] = current  # 保存用户信息
            saves[who][name]["存档日期"] = str(date.today())  # 记录存档日期
            print(saves)  # 打印调试信息
            
            # 将更新后的存档写回 JSON 文件
            with open("saves.json","w",encoding='utf-8') as file:
                json.dump(saves, file, ensure_ascii=False, indent=4)
            
            # 通知用户存档成功及当前存档数量
            wx.SendMsg(f"已存档:{name},当前数量:{len(saves[who])}", who)
    
    # 如果名称为空或不合法，则提示用户
    else:
        wx.SendMsg(f"不合法的名称:{name}", who)


# 读档
def load_save(who, name):
    # 打开存档 JSON 文件并读取内容
    with open("saves.json","r",encoding='utf-8') as file:
        saves = json.load(file)
    
    # 检查该用户是否存在名为 name 的存档
    if saves[who].get(name, None) == None:
        wx.SendMsg(f"此存档不存在:{name}", who)  # 不存在则提示用户
    else:
        # 如果存档存在，将存档内容加载到当前用户信息中
        user_info[who] = saves[who][name]
        
        # 删除存档日期字段（在当前会话中不需要）
        user_info[who].pop("存档日期")
        
        # 通知用户读取存档成功，并显示该用户当前存档数量
        wx.SendMsg(f"已读档:{name},当前数量:{len(saves[who])}", who)


# 删除存档
def remove_save(who, name):
    # 打开存档 JSON 文件并读取内容
    with open("saves.json","r",encoding='utf-8') as file:
        saves = json.load(file)
    
    # 检查该用户是否存在名为 name 的存档
    if saves[who].get(name, None) == None:
        wx.SendMsg(f"此存档不存在:{name}", who)  # 不存在则提示用户
    else:
        # 如果存档存在，则从该用户的存档中移除该存档
        saves[who].pop(name)
        
        # 将更新后的存档信息写回 JSON 文件
        with open("saves.json","w",encoding='utf-8') as file:
            json.dump(saves, file, ensure_ascii=False, indent=4)
        
        # 通知用户删除成功，并显示该用户当前存档数量
        wx.SendMsg(f"已删除:{name},当前数量:{len(saves[who])}", who)


# 向who发送存档信息
def send_saves_info(who):
    # 打开存档 JSON 文件并读取内容
    with open("saves.json", "r", encoding='utf-8') as file:
        saves = json.load(file)
    
    # 初始化存档信息字符串，第一行是表头
    info = "(存档名,角色名,创建日期)"
    
    # 遍历该用户所有存档，将每个存档的信息追加到 info 字符串中
    for save in saves[who]:
        info = info + f"\n({save},{saves[who][save]['角色']},{saves[who][save]['存档日期']})"
    
    # 添加总存档数量
    info = info + "\n" + "合计: " + str(len(saves[who]))
    
    # 将整理好的存档信息发送给用户
    wx.SendMsg(info, who)


# 通过file_name读取提示词
def get_prompt(file_name):
    # 切换到角色文件存放目录
    os.chdir(roles_path)
    try:
        # 打开指定名称的文本文件并读取内容
        with open(f"{file_name}.txt", 'r', encoding='utf-8') as file:
            content = file.read().strip()  # 去除首尾空白字符
        print(f"从{file_name}.txt读取内容")
        
        # 切换回主目录
        os.chdir(main_path)
        
        # 返回读取的内容
        return content
    except Exception as e:
        # 读取文件失败时打印错误并返回默认字符串
        print(f"读取文件失败: {e}")
        os.chdir(main_path)
        return "读取失败"

    
# 将全局user_info存到json
def save_all():
    try:
        # 将当前用户信息写入 user_info.json 文件，保证中文正常显示并美化缩进
        with open("user_info.json","w",encoding='utf-8') as file:
            json.dump(user_info,file,ensure_ascii=False,indent=4)
        
        # 将所有群聊信息写入 groups_chat_info.json 文件，保证中文正常显示并美化缩进
        with open("groups_chat_info.json","w",encoding='utf-8') as file:
            json.dump(groups_chat_info,file,ensure_ascii=False,indent=4)
        
        # 保存成功返回 True
        return True
    except Exception as e:
        # 保存失败时打印错误信息并返回 False
        print(f"保存失败:{e}")
        return False


# 单独初始化一个用户,并更新到全局user_info  
def init_user(who, role_name=default_model):
    global user_info
    # 初始化用户信息字典
    user_info[who] = {
        "角色": role_name,  # 当前角色名称
        "计数器": "0",      # 对话计数器
        "核心记忆": "",     # 用户核心记忆（可用于长期上下文）
        "历史记录":[         # 对话历史记录
            {
                "role": "system",  # 系统角色，用于存储初始提示
                "content": start_of_prompt + get_prompt(role_name)  # 拼接初始提示和角色信息
            }
        ]
    }
    # 打印初始化信息，便于调试
    print(f"初始化:{who},角色:{role_name}")


# 初始化新用户信息:并从json加载user_info
def init_user_info():
    global user_info
    # 从文件中读取已有的用户信息
    with open("user_info.json", "r", encoding='utf-8') as file:
        user_info = json.load(file)
    
    # 遍历默认用户、VIP用户和管理员
    # 若在 user_info 中不存在，则初始化该用户
    for user in default + VIP + admin:
        if user not in user_info:
            init_user(user)
    
    # 将更新后的 user_info 写回文件，保证持久化
    with open("user_info.json", "w", encoding='utf-8') as file:
        json.dump(user_info, file, ensure_ascii=False, indent=4)


# 从user_info.json加载全局user_info
def load_user_info(): 
    global user_info
    with open("user_info.json","r",encoding='utf-8') as file:
        user_info = json.load(file)


def init_save():
    # 打开存档文件并读取已有存档信息
    with open("saves.json","r",encoding='utf-8') as file:
        saves = json.load(file)
    
    # 遍历所有用户，如果该用户还没有存档，则初始化为空字典
    for user in user_info:
        if user not in saves:
            saves[user] = {} 
    
    # 将更新后的存档信息写回文件
    with open("saves.json","w",encoding='utf-8') as file:
        json.dump(saves, file, ensure_ascii=False, indent=4)


# 初始化所有组
def init_user_group():
    try:
        # 从文件中读取用户分组信息
        with open("user_groups.json", "r", encoding='utf-8') as file:
            groups = json.load(file)

        # 声明全局变量，方便后续使用
        global admin, VIP, default, group_chat

        # 将读取的数据赋值给全局变量
        admin = groups["Admin"]      # 管理员列表
        VIP = groups["VIP"]          # VIP 用户列表
        default = groups["Default"]  # 默认用户列表
        group_chat = groups["Groups"] # 群聊列表

        # 初始化每个用户信息
        init_user_info()

        # 初始化群聊信息
        init_group_chat()

        # 添加监听的群聊（如果有的话）
        add_listen_chats()

        print("初始化group成功")
        return "初始化group成功"
    except Exception as e:
        # 捕获异常并输出错误信息
        print(f"初始化失败:{e}")
        return f"初始化失败:{e}"


def increase_role_count(who, is_group_chat):
    # 打开角色列表文件，读取所有角色信息
    with open("role_list.json", "r", encoding='utf-8') as file:
        roles = json.load(file)

    # 打开同一个文件用于写入更新后的数据
    with open("role_list.json", "w", encoding='utf-8') as file:
        if is_group_chat:
            # 如果是群聊，则增加群聊角色的调用次数
            roles[groups_chat_info[who]["角色"]]["调用次数"] = str(
                int(roles[groups_chat_info[who]["角色"]]["调用次数"]) + 1
            )
        else:
            # 如果是私聊，则增加该用户角色的调用次数
            roles[user_info[who]["角色"]]["调用次数"] = str(
                int(roles[user_info[who]["角色"]]["调用次数"]) + 1
            )
        # 将更新后的角色信息写回文件
        json.dump(roles, file, ensure_ascii=False, indent=4)


def send_conversation_count(who):
    # 打开角色列表文件，读取所有角色信息
    with open("role_list.json", "r", encoding='utf-8') as file:
        roles = json.load(file)
    try:
        # 尝试获取该群聊的角色的调用次数并发送给用户
        wx.SendMsg(roles[groups_chat_info[who]["角色"]]["调用次数"], who)
    except Exception as e:
        # 如果出现异常（例如角色不存在），发送失败提示
        wx.SendMsg("获取次数失败", who)


def init_group_chat():
    global groups_chat_info
    # 读取群聊信息文件，将其加载到全局变量 groups_chat_info
    with open("groups_chat_info.json", "r", encoding='utf-8') as file:
        groups_chat_info = json.load(file)
    
    # 遍历所有已知群聊，如果群聊信息不存在，则初始化该群聊
    for group in group_chat:
        if group not in groups_chat_info:
            init_one_group_chat(group)
    
    # 将更新后的群聊信息保存回文件
    with open("groups_chat_info.json", "w", encoding='utf-8') as file:
        json.dump(groups_chat_info, file, ensure_ascii=False, indent=4)


def init_one_group_chat(group, role_name=default_model, is_reset=True):
    global groups_chat_info
    if is_reset:
        # 完全初始化群聊信息，包括角色、计数器、核心记忆、历史记录和群成员字典
        groups_chat_info[group] = {
            "角色": role_name,           # 群聊使用的角色名称
            "计数器": "0",               # 对话计数器
            "核心记忆": "",              # 群聊核心记忆内容
            "历史记录": [                # 群聊历史记录，初始化为空系统信息
                {
                    "role": "system",
                    "content": ""
                }
            ],
            "群成员": {}                 # 群成员及其信息，初始化为空字典
        }
    else:
        # 非重置模式，仅清空历史记录和核心记忆，保留其他信息
        groups_chat_info[group]["历史记录"] = []
        groups_chat_info[group]["核心记忆"] = ""
    
    # 打印初始化信息，用于调试
    print(f"初始化:{group},角色:{role_name}")

    
def send_favorability(who):
    # 初始化显示字符串，标题为“好感度列表”
    favorability_str = "好感度列表:"
    
    # 遍历群成员字典，将每个成员的好感度添加到显示字符串中
    for element in groups_chat_info[who]["群成员"]:
        favorability_str += "\n" + element + ":" + groups_chat_info[who]["群成员"][element]
    
    # 通过微信发送好感度列表给指定群聊
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
    # 无限循环，持续监听消息
    while True:
        # 获取监听到的所有消息，返回一个字典，key为聊天对象，value为消息列表
        msgs = wx.GetListenMessage()
        
        # 遍历每个聊天对象
        for chat in msgs:
            one_msg = msgs.get(chat)
            
            # 遍历该聊天对象的每条消息
            for msg in one_msg:
                print(f"msg:\n{msg}")  # 打印消息内容调试
                
                # 只处理好友消息
                if msg.type == "friend":
                    content = msg.content  # 消息内容
                    who = chat.who        # 消息发送者
                    
                    # 提取消息中的指令前缀内容
                    content = extract_prefix_content(who, content)
                    
                    # 如果提取到指令，则处理
                    if content != None:
                        # 如果是普通命令处理失败，则判断是群聊还是私聊
                        if not process_command(who, content):
                            if who in group_chat:
                                # 处理群聊消息，发送回复，并增加群聊角色调用次数
                                wx.SendMsg(process_group_chat_msg(who, content, msg.sender), who)
                                increase_role_count(who, True)
                            else:
                                # 处理私聊消息，发送回复，并增加私聊角色调用次数
                                wx.SendMsg(process_private_chat_msg(who, content), who)
                                increase_role_count(who, False)
        
        # 每次循环暂停1秒，防止CPU过高
        time.sleep(1)


def run():
    init_user_group()
    init_save()
    monitor_and_process()

run()
