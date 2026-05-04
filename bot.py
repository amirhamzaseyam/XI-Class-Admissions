import requests
import asyncio
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
import os
import urllib3
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

# SSL ওয়ার্নিং বন্ধ করার জন্য
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ----------- ১. ফ্লাস্ক সার্ভার (Render এ সচল রাখার জন্য) -----------
app = Flask('')
@app.route('/')
def home(): return "Scanner is Online & Telegram Button Added!"

def run():
    # রেন্ডার পোর্টের জন্য এনভায়রনমেন্ট ভেরিয়েবল চেক
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ----------- ২. কনফিগারেশন -----------
BOT_TOKEN = "8646130891:AAER7aF5CdKSL_5Ds1EhWK9MqnoFWnnli1I"

# সেশন মেইনটেইন করার জন্য
session = requests.Session()
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://billpay.sonalibank.com.bd/XIClassAdmission/Fee/"
}

# ----------- ৩. ডাটা স্ক্র্যাপার -----------
def get_data(tid):
    url = f"https://billpay.sonalibank.com.bd/XIClassAdmission/Home/Voucher/{tid}"
    try:
        r = session.get(url, headers=headers, timeout=15, verify=False)
        soup = BeautifulSoup(r.text, "html.parser")
        
        d = {
            "id": tid, "date": "N/A", "fee_type": "N/A", 
            "name": "N/A", "contact": "N/A", "roll": "N/A", 
            "board": "N/A", "year": "N/A", "amount": "0.00"
        }
        
        tds = soup.find_all("td")
        for i, td in enumerate(tds):
            txt = td.get_text(strip=True).replace(":", "")
            if i+1 < len(tds):
                val = tds[i+1].get_text(strip=True)
                if "Transaction Id" == txt: d["id"] = val
                elif "Date" == txt: d["date"] = val
                elif "Fee Type" == txt: d["fee_type"] = val
                elif "Student Name" == txt: d["name"] = val
                elif "Contact No" == txt: d["contact"] = val
                elif "Roll" == txt: d["roll"] = val
                elif "Board" == txt: d["board"] = val
                elif "Year" == txt: d["year"] = val
                elif "Fee Amount" == txt: d["amount"] = val
        return d
    except: return None

# ----------- ৪. রেজাল্ট প্রসেসর (WhatsApp + Telegram বাটন সহ) -----------
async def process_student_results(update_or_query, data_list):
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    final_output = "📄 <b>XI Admission Fee Result</b>\n\n"
    phones = []
    
    for i, data in enumerate(data_list, 1):
        final_output += (
            f"📄 Result {i}\n"
            f"<pre>"
            f"Transaction Id: {data['id']}\n"
            f"Student Name: {data['name']}\n"
            f"Roll: {data['roll']}\n"
            f"Board: {data['board']}\n"
            f"Year: {data['year']}\n"
            f"Contact No: {data['contact']}\n"
            f"Fee Type: {data['fee_type']}\n"
            f"Fee Amount: {data['amount']}\n"
            f"Date: {data['date']}"
            f"</pre>\n\n"
        )
        # নাম্বার ফরম্যাট ঠিক করা
        p = data["contact"].strip()[-11:]
        if len(p) >= 11 and p not in phones: phones.append(p)

    keyboard = []
    for ph in phones:
        # বাংলাদেশের কান্ট্রি কোড সহ লিঙ্ক
        full_phone = f"88{ph}"
        # হোয়াটসঅ্যাপ এবং টেলিগ্রাম বাটন পাশাপাশি
        keyboard.append([
            InlineKeyboardButton("🟢 WhatsApp", url=f"https://wa.me/{full_phone}"),
            InlineKeyboardButton("🔵 Telegram", url=f"https://t.me/+{full_phone}")
        ])
    
    await msg_source.reply_text(final_output, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

# ----------- ৫. কোর সার্চ ইঞ্জিন -----------
async def run_search(update_or_query, context, s_r, e_r):
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    status_msg = await msg_source.reply_text("⏳ <b>Scanning...</b>", parse_mode="HTML")
    
    context.user_data["current_end"] = e_r
    found_students = 0
    total_range = e_r - s_r + 1
    
    for i, roll in enumerate(range(s_r, e_r + 1), 1):
        try:
            if i == 1: session.get("https://billpay.sonalibank.com.bd/XIClassAdmission/Fee/", headers=headers, verify=False)
            
            search_url = f"https://billpay.sonalibank.com.bd/XIClassAdmission/Home/Search?searchStr={roll}"
            r = session.get(search_url, headers=headers, timeout=10, verify=False)
            
            ids = re.findall(r'Voucher/([A-Za-z0-9\-]+)', r.text)
            
            if ids:
                v_list = []
                for tid in set(ids):
                    d = get_data(tid)
                    if d and d["name"] != "N/A": v_list.append(d)
                
                if v_list:
                    student_map = {}
                    for v in v_list:
                        key = f"{v['name']}_{v['roll']}".upper()
                        if key not in student_map: student_map[key] = []
                        student_map[key].append(v)
                    
                    for key in student_map:
                        found_students += 1
                        await process_student_results(update_or_query, student_map[key])

            if i % 5 == 0 or i == total_range:
                await status_msg.edit_text(f"⏳ <b>Processing XI Admission</b>\n🔢 Roll: {roll}\n📊 Found: {found_students}\n✅ Progress: {i}/{total_range}", parse_mode="HTML")
            await asyncio.sleep(0.1)
        except: continue

    await status_msg.delete()
    await msg_source.reply_text(f"✅ Done!\n📊 Found Students: {found_students}", 
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👉 Next 500?", callback_data="next_500")]]))

# ----------- ৬. হ্যান্ডলারস -----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("XI Class Admission Fee Scanner!", 
                                   reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Start Search", callback_data="btn_ready")]]))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()
    try:
        if "-" in t:
            s, e = map(int, t.split("-"))
            await run_search(update, context, s, e)
        else: await run_search(update, context, int(t), int(t))
    except: pass

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "btn_ready":
        await query.message.reply_text("🚀 রোল বা রেঞ্জ পাঠান (উদা: 556798-556800)")
    
    elif query.data == "next_500":
        last_end = context.user_data.get("current_end", 0)
        if last_end > 0:
            await run_search(query, context, last_end + 1, last_end + 500)
        else:
            await query.message.reply_text("❌ কোনো আগের সার্চ পাওয়া যায়নি। নতুন করে রোল লিখুন।")

if __name__ == "__main__":
    keep_alive()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("🚀 Full & Final Bot Started with Telegram Button Added ✅")
    application.run_polling()
