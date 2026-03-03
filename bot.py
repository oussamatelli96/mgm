#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import telebot
from telebot import types
import requests
import random
import time
import logging
import json
from datetime import datetime
import os
import sys
import re
import threading

TOKEN = "8613281438:AAGyXhCCuG-OMKVqjxUChOr6pbZy1qAw0v4"
bot = telebot.TeleBot(TOKEN)

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('djezzy_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': "MobileApp/3.0.0",
    'Accept': "application/json",
    'Content-Type': "application/json",
    'accept-language': "ar",
    'Connection': "keep-alive"
}

REGISTERED_NUMBERS_FILE = "registered_numbers.json"
active_sessions = {}

def load_json_file(filename, default=[]):
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"خطأ في تحميل الملف {filename}: {e}")
            return default
    return default

def save_json_file(filename, data):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ الملف {filename}: {e}")
        return False

def load_registered_numbers():
    return load_json_file(REGISTERED_NUMBERS_FILE, [])

def save_registered_numbers(numbers):
    return save_json_file(REGISTERED_NUMBERS_FILE, numbers)

def save_registered_number(number_data):
    numbers = load_registered_numbers()
    numbers.append(number_data)
    save_registered_numbers(numbers)

def format_num(phone):
    phone = str(phone).strip()
    if phone.startswith('0'):
        return "213" + phone[1:]
    elif not phone.startswith('213'):
        return "213" + phone
    return phone

def generate_random_djezzy_no():
    prefix = random.choice(["077", "078", "079"])
    number = prefix + "".join([str(random.randint(0, 9)) for _ in range(7)])
    return number

def request_otp(msisdn):
    url = "https://apim.djezzy.dz/mobile-api/oauth2/registration"
    params = {
        'msisdn': msisdn,
        'client_id': "87pIExRhxBb3_wGsA5eSEfyATloa",
        'scope': "smsotp"
    }
    payload = {
        "consent-agreement": [{"marketing-notifications": False}],
        "is-consent": True
    }
    try:
        response = requests.post(url, params=params, json=payload, headers=HEADERS, timeout=10)
        logger.info(f"طلب رمز التحقق لـ {msisdn}: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"خطأ في طلب رمز التحقق: {e}")
        return None

def login_with_otp(mobile_number, otp):
    payload = {
        'otp': otp,
        'mobileNumber': mobile_number,
        'scope': "djezzyAppV2",
        'client_id': "87pIExRhxBb3_wGsA5eSEfyATloa",
        'client_secret': "uf82p68Bgisp8Yg1Uz8Pf6_v1XYa",
        'grant_type': "mobile"
    }
    try:
        res = requests.post(
            "https://apim.djezzy.dz/mobile-api/oauth2/token",
            data=payload,
            headers={'User-Agent': "MobileApp/3.0.0"},
            timeout=10
        )
        if res.status_code == 200:
            token_data = res.json()
            return f"Bearer {token_data.get('access_token')}"
        logger.error(f"فشل تسجيل الدخول: {res.status_code} - {res.text}")
        return None
    except Exception as e:
        logger.error(f"خطأ في تسجيل الدخول: {e}")
        return None

def send_invitation(token, sender, receiver):
    try:
        inv = requests.post(
            f"https://apim.djezzy.dz/mobile-api/api/v1/services/mgm/send-invitation/{sender}",
            json={"msisdnReciever": receiver},
            headers={**HEADERS, 'authorization': token},
            timeout=10
        )
        return inv.status_code in [200, 201, 202]
    except Exception as e:
        logger.error(f"خطأ في إرسال الدعوة: {e}")
        return False

def activate_reward(token, sender):
    try:
        act = requests.post(
            f"https://apim.djezzy.dz/mobile-api/api/v1/services/mgm/activate-reward/{sender}",
            json={"packageCode": "MGMBONUS1Go"},
            headers={**HEADERS, 'authorization': token},
            timeout=10
        )
        return act.status_code in [200, 201, 202]
    except Exception as e:
        logger.error(f"خطأ في تفعيل المكافأة: {e}")
        return False

def try_register_with_number(sender_number, otp, user_id, user_name, max_attempts=50):
    logger.info(f"محاولة تسجيل للرقم {sender_number} من المستخدم {user_id}")
   
    token = login_with_otp(sender_number, otp)
    if not token:
        logger.error("فشل تسجيل الدخول")
        return False, "فشل تسجيل الدخول. تأكد من الرمز وحاول مرة أخرى"
   
    success_count = 0
    failed_attempts = 0
   
    for attempt in range(max_attempts):
        target = generate_random_djezzy_no()
        target_f = format_num(target)
       
        logger.info(f"المحاولة {attempt + 1}: إرسال دعوة إلى {target}")
       
        if send_invitation(token, sender_number, target_f):
            logger.info(f"تم إرسال الدعوة بنجاح إلى {target}")
           
            try:
                request_otp(target_f)
            except:
                pass
            time.sleep(2)
           
            if activate_reward(token, sender_number):
                success_count += 1
                logger.info(f"تم تفعيل 1 جيغابايت بنجاح مع {target}")
               
                number_data = {
                    "user_id": user_id,
                    "user_name": user_name,
                    "sender": sender_number,
                    "target": target,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "success"
                }
                save_registered_number(number_data)
               
                if success_count % 5 == 0:
                    try:
                        bot.send_message(user_id, f"تم الوصول إلى {success_count} جيغابايت حتى الآن")
                    except:
                        pass
            else:
                failed_attempts += 1
                logger.warning(f"فشل تفعيل المكافأة مع {target}")
        else:
            failed_attempts += 1
            logger.warning(f"فشل إرسال الدعوة إلى {target}")
       
        time.sleep(1.5)
   
    final_message = f"اكتملت العملية! تم الحصول على {success_count} جيغابايت"
    if failed_attempts > 0:
        final_message += f"\nفشلت {failed_attempts} محاولات"
   
    return True, final_message

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "غير محدد"
    first_name = message.from_user.first_name or ""
   
    welcome_text = f"""
✨ مرحباً بك في بوت الحصول على جيغابايت مجانية ✨
📱 يساعدك البوت في الحصول على سعة إنترنت مجانية
🔹 البوت مفتوح للجميع دون قيود
🔹 أرسل رقمك الآن واتبع التعليمات
👤 معلوماتك:
• المعرف: `{user_id}`
• اسم المستخدم: @{username}
• الاسم: {first_name}
📌 للبدء:
أرسل رقم جيزي (مثال: 0770123456)
    """
   
    markup = types.InlineKeyboardMarkup()
    btn_help = types.InlineKeyboardButton("🆘 مساعدة", callback_data="help")
    btn_stats = types.InlineKeyboardButton("📊 إحصائياتي", callback_data="mystats")
    markup.add(btn_help, btn_stats)
   
    bot.reply_to(message, welcome_text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
🆘 مساعدة:
الأوامر المتاحة:
/start - بدء استخدام البوت
/help - عرض هذه المساعدة
/stats - عرض إحصائياتك الشخصية
/allstats - عرض إحصائيات الجميع

كيفية الاستخدام:
1. أرسل رقم جيزي
2. انتظر رمز التحقق عبر الرسائل القصيرة
3. أرسل الرمز للبوت
4. انتظر حتى اكتمال العملية (قد تستغرق عدة دقائق)

ملاحظات مهمة:
• يجب أن يكون الرقم من جيزي (077، 078، 079)
• تأكد من إدخال الرمز بشكل صحيح
• يقوم البوت بإرسال دعوات لأرقام عشوائية
• كل دعوة ناجحة = زيادة 1 جيغابايت

مثال:
أرسل: 0770123456
ثم أرسل الرمز: 123456
    """
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['stats'])
def stats_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "مستخدم"
   
    numbers = load_registered_numbers()
    user_numbers = [n for n in numbers if n.get('user_id') == user_id]
   
    last_use = user_numbers[-1]['timestamp'] if user_numbers else 'لا يوجد'
    total_gb = len(user_numbers)
   
    recent = ""
    for i, num in enumerate(user_numbers[-5:], 1):
        recent += f"\n {i}. {num['target']} - {num['timestamp']}"
   
    status_text = f"""
📊 إحصائياتك الشخصية:
👤 المستخدم: @{username} (`{user_id}`)
• إجمالي الجيغابايت المحصل عليها: {total_gb}
• آخر استخدام: {last_use}
• آخر 5 عمليات:{recent if recent else "\n لا توجد عمليات بعد"}
للبدء بجلسة جديدة: أرسل رقمك
    """
   
    bot.reply_to(message, status_text, parse_mode="Markdown")

@bot.message_handler(commands=['allstats'])
def allstats_command(message):
    numbers = load_registered_numbers()
   
    if not numbers:
        bot.reply_to(message, "لا توجد إحصائيات بعد")
        return
   
    total_uses = len(numbers)
    unique_users = len(set([n.get('user_id') for n in numbers if n.get('user_id')]))
   
    users_stats = {}
    for num in numbers:
        uid = num.get('user_id')
        if uid:
            if uid not in users_stats:
                users_stats[uid] = {
                    'count': 0,
                    'name': num.get('user_name', 'مستخدم'),
                    'last': num.get('timestamp')
                }
            users_stats[uid]['count'] += 1
   
    top_users = sorted(users_stats.items(), key=lambda x: x[1]['count'], reverse=True)[:10]
   
    stats_text = f"""
📊 الإحصائيات العامة:
👥 عدد المستخدمين: {unique_users}
📱 إجمالي الجيغابايت الممنوحة: {total_uses}
أبرز 10 مستخدمين:
"""
   
    for i, (uid, data) in enumerate(top_users, 1):
        stats_text += f"\n{i}. `{uid}` - {data['count']} جيغابايت"
   
    bot.reply_to(message, stats_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    text = message.text.strip()
    username = message.from_user.username or f"user_{user_id}"
   
    if user_id in active_sessions:
        session = active_sessions[user_id]
       
        if session['step'] == 'waiting_otp':
            otp = text.strip()
           
            if not re.match(r'^\d{4,6}$', otp):
                bot.reply_to(message, "الرمز غير صحيح. يجب أن يكون من 4 إلى 6 أرقام\nحاول مرة أخرى:")
                return
           
            bot.reply_to(message, "جاري معالجة الطلب... قد تستغرق العملية عدة دقائق")
           
            result, result_message = try_register_with_number(
                session['number'],
                otp,
                user_id,
                username,
                max_attempts=session.get('attempts', 50)
            )
           
            del active_sessions[user_id]
           
            if result:
                bot.reply_to(message, f"تمت العملية بنجاح\n{result_message}\n\nللبدء بجلسة جديدة، أرسل رقمًا آخر")
            else:
                bot.reply_to(message, f"فشلت العملية\n{result_message}\n\nحاول مرة أخرى بإرسال رقم جديد")
       
        return
   
    if re.match(r'^(0|213)?[567][0-9]{8}$', text.replace(' ', '')):
        number = text.replace(' ', '')
        formatted_number = format_num(number)
       
        msg = bot.reply_to(message, f"جاري إرسال رمز التحقق إلى {number}...")
       
        otp_response = request_otp(formatted_number)
       
        if otp_response and otp_response.status_code in [200, 201, 202]:
            active_sessions[user_id] = {
                'number': formatted_number,
                'step': 'waiting_otp',
                'start_time': time.time(),
                'attempts': 50
            }
           
            bot.edit_message_text(
                "تم إرسال الرمز بنجاح\nأرسل الرمز الذي تلقيته:",
                chat_id=message.chat.id,
                message_id=msg.message_id,
                parse_mode="Markdown"
            )
        else:
            bot.edit_message_text(
                "فشل إرسال الرمز\nتأكد من الرقم وحاول مرة أخرى\nإذا استمر الخطأ، قد يكون الرقم غير صالح",
                chat_id=message.chat.id,
                message_id=msg.message_id,
                parse_mode="Markdown"
            )
   
    else:
        bot.reply_to(message, """
رقم غير صالح
يرجى إرسال رقم جيزي صحيح:
• مثال: 0770123456
• أو: 0798765432
• أو: 213770123456
للمساعدة: /help
        """, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "help":
        bot.answer_callback_query(call.id, "جاري عرض المساعدة...")
        help_command(call.message)
   
    elif call.data == "mystats":
        bot.answer_callback_query(call.id, "جاري عرض إحصائياتك...")
        stats_command(call.message)

def main():
    print("=" * 60)
    print(" بوت الحصول على جيغابايت - بدون قيود ")
    print("=" * 60)
    print("\nجاري تشغيل البوت...")
   
    if not os.path.exists(REGISTERED_NUMBERS_FILE):
        save_registered_numbers([])
        print("تم إنشاء ملف registered_numbers.json")
   
    print("البوت يعمل الآن")
    print("=" * 60)
   
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except KeyboardInterrupt:
        print("\nتم إيقاف البوت")
    except Exception as e:
        logger.error(f"خطأ في البوت: {e}")
        print(f"\nخطأ: {e}")

if __name__ == "__main__":
    main()