import requests
import os
import datetime
import sqlite3
import json
import base64
import re
import time
import random
import string
import threading
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, ConversationHandler, CallbackQueryHandler

# 定义频道名称
channel_name = "@BOTTGCS"

# 建立或连接到SQLite数据库
conn = sqlite3.connect("qingshuang.db")
cursor = conn.cursor()

    
# 创建用户数据表
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        last_checkin_date TEXT,
        points INTEGER,
        is_banned INTEGER DEFAULT 0
    )
''')

# 创建卡密数据表
cursor.execute('''
    CREATE TABLE IF NOT EXISTS activation_codes (
        code TEXT PRIMARY KEY,
        points INTEGER,
        used INTEGER
    )
''')

# 创建会员数据表
cursor.execute('''
    CREATE TABLE IF NOT EXISTS members (
        user_id INTEGER PRIMARY KEY,
        is_vip INTEGER DEFAULT 0,
        vip_expire_date TEXT
    )
''')

conn.commit()

# 用于标识管理员的用户ID
admin_user_id = 6751435480  # 请替换为你的管理员用户ID

# 定义状态常量
SELECTING_ACTION, CREATING_ACTIVATION_CODE = range(2)
# 定义状态常量
SELECTING_ACTION, CREATING_ACTIVATION_CODE, QUERYING_INFO = range(3)
# 存储管理员正在创建的卡密
admin_creating_activation_code = {}

#/start指令
#包括校验他是否关注频道
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    # 检查用户是否是频道的成员
    is_member = await context.bot.get_chat_member(channel_name, user_id)
    if is_member.status == "member" or is_member.status == "administrator" or is_member.status == "creator":
        welcome_message = "欢迎使用青霜-政务社工机器人\n输入 /list 查看指令列表\n输入 /qd 进行签到\n群组: @\n频道: @"
        await update.message.reply_text(welcome_message)
    else:
        await update.message.reply_text("请先关注频道 @fjpeople，然后再使用机器人。")

async def list_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    command_list = "📋 指令列表:\n\n/me - 获取个人详情\n/vip - 获取vip详情\n/qd - 签到\n/km [卡密] - 充值积分\n/qgxj [姓名 身份证] - 全国学籍(在读) 1分\n/sxdt [身份证] - 陕西大头 3分\n/lncy [身份证] - 辽宁常用号 1分\n/sxyh [身份证] - 陕西银行 1分\n/hljym [身份证] - 黑龙江疫苗(带预留) 1分\n/lnfc [身份证] - 辽宁房产 1分 维护\n/gzyxq [姓名 身份证] - 广州有效期 1分"
    await update.message.reply_text(command_list)

#/qd指令
async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    today = datetime.date.today().isoformat()

    # 查询用户签到记录
    cursor.execute("SELECT last_checkin_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row is None or row[0] != today:
        # 用户尚未签到或上次签到不是今天
        #增加签到增加分数改后面的+2，
        cursor.execute("INSERT OR REPLACE INTO users (user_id, last_checkin_date, points) VALUES (?, ?, COALESCE((SELECT points FROM users WHERE user_id = ?), 0) + 2)",
                       (user_id, today, user_id))
        conn.commit()
        await update.message.reply_text("签到成功！你获得了2积分。")
    else:
        await update.message.reply_text("你今天已经签到过了。")

#/km指令
async def redeem_activation_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    args = text.split()

    if len(args) != 2:
        await update.message.reply_text("请提供一个有效的卡密，例如：/km ABC123")
        return

    code = args[1].strip().upper()

    # 查询卡密是否存在且未使用
    cursor.execute("SELECT points FROM activation_codes WHERE code = ? AND used = 0", (code,))
    row = cursor.fetchone()

    if row:
        points = row[0]

        # 更新用户积分
        cursor.execute("INSERT OR REPLACE INTO users (user_id, last_checkin_date, points) VALUES (?, ?, COALESCE((SELECT points FROM users WHERE user_id = ?), 0) + ?)",
                       (user_id, datetime.date.today().isoformat(), user_id, points))

        # 标记卡密为已使用
        cursor.execute("UPDATE activation_codes SET used = 1 WHERE code = ?", (code,))
        conn.commit()

        await update.message.reply_text(f"充值成功！你获得了{points}积分。")
    else:
        await update.message.reply_text("无效的卡密或卡密已被使用。")

async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    # 只有管理员可以查看机器人统计信息
    if user_id != admin_user_id:
        await update.message.reply_text("只有管理员才能查看机器人统计信息。")
        return

    # 查询用户总数
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]

    stats_message = f"用户总数: {user_count}"
    await update.message.reply_text(stats_message)

#/me指令
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    points = cursor.fetchone()

    if points:
        await update.message.reply_text(f"您的用户ID是：{user_id}\n您剩余的积分是：{points[0]}")
    else:
        await update.message.reply_text("无法获取您的个人详情。")

#/admin指令
async def admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if user_id != admin_user_id:
        await update.message.reply_text("只有管理员才能查看管理员指令列表。")
        return

    admin_command_list = "👑 管理员指令列表:\n\n1. /bot - 查看机器人统计信息\n2. /xzkm - 新增卡密并充值积分\n3. /xzvip - 新增vip卡密"
    await update.message.reply_text(admin_command_list)
#/xzkm指令
async def create_activation_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id

    if user_id != admin_user_id:
        await update.message.reply_text("只有管理员才能创建新的卡密。")
        return

    admin_creating_activation_code[user_id] = {"step": 0, "code": "", "points": 0}
    await update.message.reply_text("请输入卡密内容：")
    return CREATING_ACTIVATION_CODE

async def create_activation_code_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in admin_creating_activation_code:
        await update.message.reply_text("你没有权限创建卡密。")
        return ConversationHandler.END

    if admin_creating_activation_code[user_id]["step"] == 0:
        # 输入卡密内容
        admin_creating_activation_code[user_id]["code"] = text.strip().upper()
        await update.message.reply_text("请输入要增加的积分数量：")
        admin_creating_activation_code[user_id]["step"] = 1
    elif admin_creating_activation_code[user_id]["step"] == 1:
        # 输入积分数量
        try:
            points = int(text)
            admin_creating_activation_code[user_id]["points"] = points

            # 检查卡密是否已存在
            cursor.execute("SELECT code FROM activation_codes WHERE code = ?", (admin_creating_activation_code[user_id]["code"],))
            existing_code = cursor.fetchone()

            if existing_code:
                await update.message.reply_text("卡密已存在，请使用其他卡密内容。")
                admin_creating_activation_code.pop(user_id)
                return ConversationHandler.END

            # 创建新的卡密并充值积分
            cursor.execute("INSERT INTO activation_codes (code, points, used) VALUES (?, ?, 0)",
                           (admin_creating_activation_code[user_id]["code"], admin_creating_activation_code[user_id]["points"]))
            conn.commit()

            await update.message.reply_text(f"新卡密已创建成功，并充值了{points}积分。")
            admin_creating_activation_code.pop(user_id)
            return ConversationHandler.END
        except ValueError:
            await update.message.reply_text("请输入有效的积分数量。")

    return CREATING_ACTIVATION_CODE

async def cancel_create_activation_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id

    if user_id not in admin_creating_activation_code:
        await update.message.reply_text("你没有权限创建卡密。")
        return ConversationHandler.END

    admin_creating_activation_code.pop(user_id)
    await update.message.reply_text("创建卡密已取消。")
    return ConversationHandler.END
#VIP部分
#/xzvip和/vipkm    
# 生成随机卡密
def generate_activation_code(length):
    characters = string.ascii_uppercase + string.digits
    code = ''.join(random.choice(characters) for _ in range(length))
    return code

# 为其他用户创建会员并生成卡密
async def create_vip_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    args = text.split()

    if len(args) != 2:
        await update.message.reply_text("请提供一个有效的时长，例如：/xzvip 30")
        return

    try:
        duration = int(args[1])
        if duration <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("请输入一个有效的正整数时长，例如：/xzvip 30")
        return

    # 生成随机卡密
    activation_code = generate_activation_code(8)

    # 计算会员到期日期
    current_date = datetime.date.today()
    expire_date = current_date + datetime.timedelta(days=duration)

    # 保存卡密信息，以供其他用户兑换
    cursor.execute("INSERT INTO activation_codes (code, points, used) VALUES (?, ?, 0)",
                   (activation_code, duration))
    conn.commit()

    await update.message.reply_text(f"已成功生成卡密：{activation_code}\n会员到期日期：{expire_date}")

async def redeem_vip_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    args = text.split()

    if len(args) != 2:
        await update.message.reply_text("请提供一个有效的卡密，例如：/vipkm ABC12345")
        return

    code = args[1].strip().upper()

    # 查询卡密是否存在且未使用
    cursor.execute("SELECT points FROM activation_codes WHERE code = ? AND used = 0", (code,))
    row = cursor.fetchone()

    if row:
        duration = row[0]

        # 更新用户VIP会员信息
        cursor.execute("INSERT OR REPLACE INTO members (user_id, is_vip, vip_expire_date) VALUES (?, 1, ?)",
                       (user_id, datetime.date.today() + datetime.timedelta(days=duration)))
        conn.commit()

        # 标记卡密为已使用
        cursor.execute("UPDATE activation_codes SET used = 1 WHERE code = ?", (code,))
        conn.commit()

        await update.message.reply_text(f"充值成功！您已成为VIP会员，到期日期：{datetime.date.today() + datetime.timedelta(days=duration)}")
    else:
        await update.message.reply_text("无效的卡密或卡密已被使用。")

async def check_vip_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    # 查询用户是否是VIP会员
    cursor.execute("SELECT is_vip, vip_expire_date FROM members WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row:
        is_vip = row[0]
        expire_date = row[1]

        if is_vip:
            await update.message.reply_text(f"您是VIP会员，到期日期：{expire_date}")
        else:
            await update.message.reply_text("您是普通会员，无VIP特权")
    else:
        await update.message.reply_text("您是普通会员，无VIP特权")

#全国学籍 1积分次
async def query_qgxj_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    args = text.split()

    # 检查命令参数是否正确
    if len(args) != 3:
        await update.message.reply_text("请提供有效的姓名和身份证号，例如：/qgxj 张三 1234567890")
        return

    # 检查用户是否有足够积分扣除
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    user_points = cursor.fetchone()

    if user_points and user_points[0] >= 1:
        userName = args[1]
        sfz = args[2]
        loginInfo = 'G' + sfz
        password = sfz[12:18]

        sourceId = 1

        url = 'https://service-k329zabl-1251413566.sh.apigw.tencentcs.com/client/Author/userName/login'
        headers = {
            'Host': 'service-k329zabl-1251413566.sh.apigw.tencentcs.com',
            'Connection': 'keep-alive',
            'Content-Length': '93',
            'access-token': '',
            'x-date': 'Mon, 07 Aug 2023 09:37:55 GMT',
            'source': '1',
            'charset': 'utf-8',
            'content-type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 7.1.2; 2112123AC Build/N2G47H; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/111.0.5563.116 Mobile Safari/537.36 XWEB/5197 MMWEBSDK/20230504 MMWEBID/7849 MicroMessenger/8.0.37.2380(0x28002537) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 MiniProgramEnv/android',
            'authorization': 'hmac id="AKID8cQp38Gnlim99v0ujA74cBwXBsvo9prBp4gi", algorithm="hmac-sha1", headers="x-date source", signature="59CM6PFDaThO2ayE1mE8KCyFPIA="',
            'Accept-Encoding': 'gzip,compress,br,deflate',
            'sourceid': '1',
            'Referer': 'https://servicewechat.com/wx5e64e98fbbb4dd8b/37/page-frame.html'
        }

        data = {
            'userName': userName,
            'loginInfo': loginInfo,
            'password': password,
            'sourceId': sourceId
        }

        response = requests.post(url, headers=headers, data=json.dumps(data))
        response_json = response.json()

        response_data = response_json.get('data')

        if response_data:
            # 扣除1积分
            cursor.execute("UPDATE users SET points = points - 1 WHERE user_id = ?", (user_id,))
            conn.commit()

            # 获取查询结果文字信息
            pinyinName = response_data.get('pinyinName')
            school_or_org = response_data.get('schoolOrOrg')
            grade_name = response_data.get('gradeName')

            response_text = f'姓名: {pinyinName}\n学校: {school_or_org}\n年级: {grade_name}'

            # 发送文字信息给用户
            await update.message.reply_text(response_text)
        else:
            await update.message.reply_text('查询失败')
    else:
        await update.message.reply_text("你的积分不足，无法进行查询。")

#辽宁常用号 1积分一次
async def query_lncy_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    args = text.split()

    # 检查命令参数是否正确
    if len(args) != 2:
        await update.message.reply_text("请提供有效的身份证号，例如：/lncy 1234567890")
        return

    # 检查用户是否有足够积分扣除
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    user_points = cursor.fetchone()

    if user_points and user_points[0] >= 1:
        id_number = args[1]

        api_url = f"https://ihrss.neupaas.com:10443/passport-liaoyang/pub/console/si211000/authNew/validateIdNumber/MOBILE/{id_number}"

        response = requests.get(api_url)

        if response.status_code == 200:
            data = response.json()

            # 检查是否存在zwwMobile字段
            if 'zwwMobile' in data:
                zww_mobile = data['zwwMobile']

                # 发送身份证和常用号给用户
                await update.message.reply_text(f"身份证: {id_number}\n常用号: {zww_mobile}")

                # 扣除1积分
                cursor.execute("UPDATE users SET points = points - 1 WHERE user_id = ?", (user_id,))
                conn.commit()
            else:
                await update.message.reply_text("查询失败")
        else:
            await update.message.reply_text(f"请求失败，状态码: {response.status_code}")
    else:
        await update.message.reply_text("你的积分不足，无法进行查询。")

# 陕西银行
async def query_sxyh_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    args = text.split()

    # 检查命令参数是否正确
    if len(args) != 2:
        await update.message.reply_text("请提供有效的身份证号，例如：/sxyh 1234567890")
        return

    # 检查用户是否有足够积分扣除
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    user_points = cursor.fetchone()

    if user_points and user_points[0] >= 1:
        id_number = args[1]

        url = "http://rszwfw.qinyunjiuye.cn:17007/getData.jspx"

        headers = {
            "Host": "rszwfw.qinyunjiuye.cn:17007",
            "Connection": "keep-alive",
            "Content-Length": "79",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "http://rszwfw.qinyunjiuye.cn:17007",
            "Referer": "http://rszwfw.qinyunjiuye.cn:17007/service/158578.jhtml",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cookie": "sxwt_cms=tsrrKLW_JxDvPuGCosXNWXb8PsyjyYOBfyd9Gz8wZXiTcTzVZJpT!-1863590705; SF_cookie_91=60201572; _gscu_471961945=96162429qhgok779; _gscbrs_471961945=1; _gscs_471961945=96162429a7h85t79|pv:20"
        }

        data = {
            "authorityid": "158587",
            "methodname": "PSBZCX1001",
            "AAC002": id_number,
            "notkeyflag": "1"
        }

        response = requests.post(url, headers=headers, data=data)
        result = response.json()
        success = result["success"]

        if success:
            list_result_set = result["lists"]["resultset"]["list"]
            if list_result_set:
                for item in list_result_set:
                    aac004_desc = item["aac004_desc"]
                    bab502_desc = item["bab502_desc"]
                    aac003 = item["aac003"]
                    aac005_desc = item["aac005_desc"]
                    aac203 = item["aac203"]
                    aaz502_desc = item["aaz502_desc"]
                    aae006 = item["aae006"]
                    aae005 = item["aae005"]
                    aac002 = item["aac002"]

                    response_text = f"姓名: {aac003}\n性别: {aac004_desc}\n民族: {aac005_desc}\n证件类型: {bab502_desc}\n证件号码: {aac002}\n户籍地址: {aae006}\n联系电话: {aae005}\n银行卡号: {aac203}\n银行名称: {aaz502_desc}"

                    # 发送身份证信息给用户
                    await update.message.reply_text(response_text)

                    # 扣除1积分
                    cursor.execute("UPDATE users SET points = points - 1 WHERE user_id = ?", (user_id,))
                    conn.commit()
            else:
                await update.message.reply_text("未找到身份证信息")
        else:
            message = result["fieldData"]["message"]
            code = result["fieldData"]["code"]
            await update.message.reply_text(f"查询失败\n错误信息: {message}\n错误代码: {code}")
    else:
        await update.message.reply_text("你的积分不足，无法进行查询。")

#黑龙江疫苗接种信息 1积分一次
async def query_hljym_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    args = text.split()

    # 检查命令参数是否正确
    if len(args) != 2:
        await update.message.reply_text("请提供有效的身份证号，例如：/hljym 230103198807141319")
        return

    # 检查用户是否有足够积分扣除
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    user_points = cursor.fetchone()

    if user_points and user_points[0] >= 1:
        id_number = args[1]

        r1 = requests.post(
            'https://ejk.home-e-care.com/ncov_InoDetail/QueryInoDetail',
            params=f'name=张三&idcard={id_number}&patientTel=18611451419'
        )

        if json.loads(r1.text)['Status'] == 'SUCCESS':
            r2 = requests.get(
                f"https://ejk.home-e-care.com/ncov_InoDetail/ResultSeal?id={json.loads(r1.text)['Data']}&type=2"
            )

            data1 = [i[:-1] for i in re.findall('<div class="item-title label">(.*)</div>', r2.text)]
            data2 = [i.strip() for i in re.findall('<div class="item-input">\r\n(.*)\r\n', r2.text)]
            personal_data = []
            for i in range(len(data1)):
                personal_data.append((data1[i], data2[i]))

            vaccination_data = []
            data3 = re.findall('<span>(.*) &nbsp;&nbsp;&nbsp; (.*)</span>', r2.text)
            data4 = re.findall('<div>(.*)：(.*)</div>', r2.text)
            data4_divided = [data4[i:i+4] for i in range(0, len(data4), 4)]
            for i in range(len(data3)):
                vaccination_data.append((('疫苗名称', data3[i][1]), ('接种时间', data3[i][0]), data4_divided[i]))

            response_text = '查询成功\n'
            for i in personal_data:
                response_text += f'{i[0]}： {i[1]}\n'
            response_text += '-' * 125 + '\n'
            for i in vaccination_data:
                response_text += f'{i[0][0]}： {i[0][1]}\n'
                response_text += f'{i[1][0]}： {i[1][1]}\n'
                for j in i[2]:
                    response_text += f'{j[0]}： {j[1]}\n'
                response_text += '~' * 10 + '\n'

            # 发送疫苗接种信息给用户
            await update.message.reply_text(response_text)

            # 扣除1积分
            cursor.execute("UPDATE users SET points = points - 1 WHERE user_id = ?", (user_id,))
            conn.commit()
        else:
            await update.message.reply_text('查询失败')
    else:
        await update.message.reply_text("你的积分不足，无法进行查询。")

import requests
import json

#辽宁房产 1积分1次
async def query_lnbdc_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    args = text.split()

    # 检查命令参数是否正确
    if len(args) != 3:
        await update.message.reply_text("请提供有效的姓名和身份证号，例如：/lnbdc 张三 230103198807141319")
        return

    # 检查用户是否有足够积分扣除
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    user_points = cursor.fetchone()

    if user_points and user_points[0] >= 1:
        zjhm = args[2]
        qlrmc = args[1]

        url = "https://app.bm.shenyang.gov.cn:10003/service"
        headers = {
            "Host": "app.bm.shenyang.gov.cn:10003",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": "https://app.bm.shenyang.gov.cn:10004/",
        }
        data = {
            "service": "BDCCX_CQ",
            "param": '{"ZJHM": "身份证", "QLRMC": "名字"}'
        }
        data["param"] = data["param"].replace("名字", qlrmc).replace("身份证", zjhm)
        response = requests.post(url, headers=headers, data=data)

        if response.status_code == 200:
            response_json = json.loads(response.text)

            if response_json:
                result = response_json[0]
                formatted_result = [
                    f"房产类型：{result['GHYT']}",
                    f"房产地址：{result['ZL']}",
                    f"办证日期：{result['DJRQ']}",
                    f"房产证号：{result['BDCZH']}",
                ]
                response_text = "\n".join(formatted_result)

                # 发送查询结果给用户
                await update.message.reply_text(response_text)

                # 扣除1积分
                cursor.execute("UPDATE users SET points = points - 1 WHERE user_id = ?", (user_id,))
                conn.commit()
            else:
                await update.message.reply_text('未找到相关信息')
        else:
            await update.message.reply_text('查询失败')
    else:
        await update.message.reply_text("你的积分不足，无法进行查询。")

#广州有效期 1分1次
async def query_gzyxq_info(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    args = text.split()

    # 检查命令参数是否正确
    if len(args) != 3:
        await update.message.reply_text("请提供有效的姓名和身份证号，例如：/gzyxq 姓名 身份证")
        return

    name = args[1]
    ID_card = args[2]

    # 执行查询函数
    response_text = await execute_gzyxq_query(user_id, name, ID_card)

    # 发送查询结果给用户
    await update.message.reply_text(response_text)

# 查询函数
async def execute_gzyxq_query(user_id, name, ID_card):
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        response = requests.get(url="https://gzhzyw.gzjd.gov.cn/hzyw/sfzjd/jdcx.do?gmsfhm=" + ID_card, headers=headers).json()
    except:
        response = []

    if len(response) > 3:
        # 转换 response 为字符串
        response_text = json.dumps(response, indent=4, ensure_ascii=False)

        # 扣除1积分（假设你已经有了相应的数据库连接和游标）
        cursor.execute("UPDATE users SET points = points - 1 WHERE user_id = ?", (user_id,))
        conn.commit()

        return f"姓名：{name}\n身份证号：{ID_card}\n查询结果：\n{response_text}"
    else:
        return f"姓名：{name}\n身份证号：{ID_card}\n未找到相关信息"

#江西神父 2积分一次
async def query_jxsf_info(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    args = text.split()

    # 检查命令参数是否正确
    if len(args) != 2:
        await update.message.reply_text("请提供有效的身份证号，例如：/jxsf 身份证")
        return

    ID_card = args[1]

    # 检查用户是否有足够积分扣除
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    user_points = cursor.fetchone()

    if user_points and user_points[0] >= 5:
        # 扣除2积分
        cursor.execute("UPDATE users SET points = points - 5 WHERE user_id = ?", (user_id,))
        conn.commit()

        # 执行查询函数
        await execute_jxsf_query(user_id, ID_card, update)
    else:
        await update.message.reply_text("你的积分不足，无法进行查询。")

# 查询函数
async def execute_jxsf_query(user_id, ID_card, update):
    url = "https://gft2.fzyjszx.com/fztService/license/getLicense"
    headers = {"content-type": "application/x-www-form-urlencoded; charset=UTF-8"}

    data = f"itemCode=361000-000201007000-QT-016-10&itemName=%E6%95%99%E8%82%B2%E6%95%91%E5%8A%A9&idCard={ID_card}"

    response = requests.post(url, headers=headers, data=data)

    if response.status_code == 200 and response.json()['code'] == "200":
        idcard = data.split('&')[-1][8:]  # 从data中提取身份证号码
        photo = response.json()['data'][0]['fileData']
        photo_pdf = base64.b64decode(photo)

        # 以身份证号码为文件名保存PDF文件到当前目录
        pdf_path = f'3{idcard}.pdf'

        with open(pdf_path, 'wb') as f:
            f.write(photo_pdf)

        # 发送PDF文件给用户
        await update.message.reply_document(document=open(pdf_path, 'rb'))

        response_text = f"3{idcard}，查询成功！"
    else:
        response_text = f"3{data.split('&')[-1][8:]}，查询失败"

    # 发送查询结果给用户
    await update.message.reply_text(response_text)

#江苏神父 2分一次
def get_jiangsu_id_card(id_card):

    serverUrl = "https://www.wzwuyouban.com/gsp/szwz/xzwx10011"
    
    params = {"keyValue": id_card, "keyValueTwo": ""}
    
    txnBodyCom = {
        "appToken": "123456",
        "catalogID": "58FBE506CB031D4FE050C8ACD3003317",
        "router_type": "applet",
        "fileType": "pdf",
        "appId": "01",
        "matter_id": "111",
        "params": params
    }
    
    txnCommCom = {
        "txnIttChnlCgyCode": "AC02C011",
        "txnIttChnlId": "C0081234567890987654321"
    }
    
    requestBody = {"txnCommCom": txnCommCom, "txnBodyCom": txnBodyCom}
    
    headers = {
        "c-app-id": "GSP_APP_001",
        "c-tenancy-id": "320506000000",
        "c-business-id": "1",
        "Content-Type": "application/json",
        "Referer": "https://servicewechat.com/wx7ce51f10e10c47b6/12/page-frame.html"
    }
    
    try:
        response = requests.post(serverUrl, data=json.dumps(requestBody), headers=headers)
        if response.status_code == 200:
            pass
    except Exception as e:
        return None
    
    if response:
        try:
            node = json.loads(response.text)
            responseBodyString = node.get("C-Response-Body")
            responseBody = json.loads(responseBodyString)
            status = responseBody.get("status")
            code = status.get("code")
            if code and code != "1":
                objNm = responseBody.get("custom").get("ObjNm")
                fileUrl = f"https://www.wzwuyouban.com/image-service/downloadImage?bucketId=GSP_PUBLIC&C-App-Id=GSP_APP_002&ObjNm={objNm}&C-Tenancy-Id=320506000000"
                headers = {"Referer": "https://servicewechat.com/wx7ce51f10e10c47b6/12/page-frame.html"}
                base64_str = get_file_base64(fileUrl, headers)
                with open(f"{id_card}-身份证.pdf", "wb") as f:
                    f.write(base64.b64decode(base64_str))
                return f"{id_card}-身份证.pdf"
            else:
                return None
        except Exception as e:
            return None
    else:
        return None

def get_file_base64(url, headers):
    response = requests.get(url, headers=headers)
    return base64.b64encode(response.content).decode()

async def jssf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    command, id_card = text.split(" ", 1)

    # 检查用户是否有足够积分扣除
    user_id = update.effective_user.id
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    user_points = cursor.fetchone()

    if user_points and user_points[0] >= 5:
        # 扣除1积分
        cursor.execute("UPDATE users SET points = points - 5 WHERE user_id = ?", (user_id,))
        conn.commit()

        if len(id_card) == 18:
            pdf_filename = get_jiangsu_id_card(id_card)
            if pdf_filename:
                with open(pdf_filename, "rb") as pdf_file:
                    await update.message.reply_document(pdf_file)

                # 删除生成的PDF文件
                os.remove(pdf_filename)
            else:
                await update.message.reply_text("无信息或输入的信息有误。")
        else:
            await update.message.reply_text("无效的身份证号码，请输入正确的18位身份证号码。")
    else:
        await update.message.reply_text("你的积分不足，无法进行查询。")
 
# 定义查询山西电子图功能的命令处理函数
async def query_sxdt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    args = text.split()

    # 检查命令参数是否正确
    if len(args) < 2:
        await update.message.reply_text("请提供有效的身份证号码，例如：/sxdt 230103198807141319 230104199305124210")
        return

    # 检查用户是否有足够积分扣除
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    user_points = cursor.fetchone()

    if user_points and user_points[0] >= 3:
        aac002_list = args[1:]

        for aac002 in aac002_list:
            url = "http://rszwfw.qinyunjiuye.cn:17007/common/getData2.jspx"
            headers = {
                "Host": "rszwfw.qinyunjiuye.cn:17007",
                "Connection": "keep-alive",
                "Content-Length": "81",
                "Accept": "application.json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "http://rszwfw.qinyunjiuye.cn:17007",
                "Referer": "http://rszwfw.qinyunjiuye.cn:17007/service/12677156.jhtml",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cookie": "_gscu_471961945=96162429qhgok779; _gscbrs_471961945=1; sxwt_cms=AgYF9kO_1nOxNdSff1yseauqzemFNN8Ai6OkYJNg0yKc1BVlVc4q!-1863590705; SF_cookie_91=60201572; _gscs_471961945=t96612362i88o2g20|pv:2"
            }

            data = {
                'authorityid': '12677306',
                'methodname': 'PSBKCX2032',
                'AAC002': aac002,
                'notkeyflag': '1'
            }

            response = requests.post(url, headers=headers, data=data)

            # 解析 JSON 数据
            data = json.loads(response.text)

            try:
                # 获取 base64 编码的图片数据
                base64_image_data = data['fieldData']['output']['resultset']['row']['baz150']

                # 解码 base64 数据
                image_binary = base64.b64decode(base64_image_data)

                # 将图片保存到以身份证号码命名的文件中
                file_name = f'{aac002}.jpg'
                with open(file_name, 'wb') as f:
                    f.write(image_binary)
                cursor.execute("UPDATE users SET points = points - 3 WHERE user_id = ?", (user_id,))
                conn.commit()
                # 发送图片给用户
                with open(file_name, 'rb') as photo:
                    await context.bot.send_photo(user_id, photo=photo)
                os.remove(file_name)

                await update.message.reply_text(f' {aac002} 查询成功')
            except KeyError:
                await update.message.reply_text(f'身份证号码 {aac002} 的图片数据未找到')
    else:
        await update.message.reply_text("你的积分不足，无法进行查询。")

               
app = ApplicationBuilder().token("7588038814:AAFRnuSZ5F48H-EnV9XZM_QSveQ9RbJi80A").build()

#/xzkm指令的，不能删除
activation_code_handler = ConversationHandler(
    entry_points=[CommandHandler("xzkm", create_activation_code)],
    states={
        CREATING_ACTIVATION_CODE: [
            MessageHandler(None, create_activation_code_content),
            CommandHandler("cancel", cancel_create_activation_code),
        ]
    },
    fallbacks=[],
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("list", list_commands))
app.add_handler(CommandHandler("qd", checkin))
app.add_handler(CommandHandler("km", redeem_activation_code))
app.add_handler(CommandHandler("bot", bot_stats))
app.add_handler(CommandHandler("me", my_profile))
app.add_handler(CommandHandler("admin", admin_commands))
app.add_handler(CommandHandler("xzvip", create_vip_membership))
#app.add_handler(CommandHandler("vipkm", redeem_vip_membership))
app.add_handler(CommandHandler("vip", check_vip_membership))
app.add_handler(CommandHandler("qgxj", query_qgxj_info))
app.add_handler(CommandHandler("lncy", query_lncy_info))
app.add_handler(CommandHandler("sxyh", query_sxyh_info))
app.add_handler(CommandHandler("hljym", query_hljym_info))
app.add_handler(CommandHandler("lnfc", query_lnbdc_info))
app.add_handler(CommandHandler("gzyxq", query_gzyxq_info))
app.add_handler(CommandHandler("sxdt", query_sxdt))
#下面那个是xzkm要用的
app.add_handler(activation_code_handler)

app.run_polling()
