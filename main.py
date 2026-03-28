import discord
from discord.ext import commands
import google.generativeai as genai
import os
import json
import asyncio
from datetime import datetime

# ==================== المتغيرات ====================
TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
OWNER_ID = int(os.getenv('OWNER_ID', '0'))

# ==================== تهيئة Gemini ====================
genai.configure(api_key=GEMINI_API_KEY)

# قائمة النماذج (البوت يجربها و يختار المناسب)
MODELS_PRIORITY = [
    'models/gemini-2.5-pro-preview-tts',
    'models/gemini-3-pro-preview',
    'models/gemini-2.0-flash-lite',
]

GENERATION_CONFIG = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048,
}

# اختيار أفضل نموذج تلقائياً
def select_best_model():
    for model_name in MODELS_PRIORITY:
        try:
            test_model = genai.GenerativeModel(model_name)
            test_model.generate_content("test")
            print(f"✅ النموذج: {model_name}")
            return model_name
        except:
            continue
    return MODELS_PRIORITY[2]

SELECTED_MODEL = select_best_model()
model = genai.GenerativeModel(
    model_name=SELECTED_MODEL,
    generation_config=GENERATION_CONFIG,
)

# ==================== إعدادات البوت ====================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

CHANNELS_FILE = 'active_channels.json'

def load_active_channels():
    try:
        if os.path.exists(CHANNELS_FILE):
            with open(CHANNELS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_active_channels(channels):
    with open(CHANNELS_FILE, 'w') as f:
        json.dump(channels, f)

active_channels = load_active_channels()

def is_owner(interaction):
    return interaction.user.id == OWNER_ID

# ==================== الأحداث ====================
@bot.event
async def on_ready():
    print(f'✅ البوت شغال: {bot.user.name}')
    await bot.tree.sync()
    print('✅ الأوامر جاهزة')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    channel_id = str(message.channel.id)
    if channel_id not in active_channels or not active_channels[channel_id]:
        await bot.process_commands(message)
        return
    
    if bot.user in message.mentions:
        prompt = message.content.replace(f'<@{bot.user.id}>', '').strip()
        
        if not prompt:
            await message.reply("👋 أرسل سؤالك")
            return
        
        async with message.channel.typing():
            try:
                response = model.generate_content(prompt)
                if response.text:
                    # تقسيم الرسالة الطويلة
                    if len(response.text) > 2000:
                        for i in range(0, len(response.text), 2000):
                            await message.channel.send(response.text[i:i+2000])
                    else:
                        await message.channel.send(response.text)
                else:
                    await message.reply("❌ ماقدرت أرد")
            except Exception as e:
                await message.reply(f"❌ خطأ: {e}")
    
    await bot.process_commands(message)

# ==================== الأوامر ====================
@bot.tree.command(name="تشغيل", description="تفعيل البوت في القناة")
async def enable_bot(interaction: discord.Interaction):
    if not is_owner(interaction):
        await interaction.response.send_message("⛔ للمطور فقط", ephemeral=True)
        return
    
    channel_id = str(interaction.channel_id)
    active_channels[channel_id] = True
    save_active_channels(active_channels)
    await interaction.response.send_message(f"✅ تم تشغيل البوت في {interaction.channel.mention}")

@bot.tree.command(name="ايقاف", description="إيقاف البوت في القناة")
async def disable_bot(interaction: discord.Interaction):
    if not is_owner(interaction):
        await interaction.response.send_message("⛔ للمطور فقط", ephemeral=True)
        return
    
    channel_id = str(interaction.channel_id)
    if channel_id in active_channels and active_channels[channel_id]:
        active_channels[channel_id] = False
        save_active_channels(active_channels)
        await interaction.response.send_message(f"⏹️ تم إيقاف البوت في {interaction.channel.mention}")
    else:
        await interaction.response.send_message("⚠️ البوت غير مفعل", ephemeral=True)

@bot.tree.command(name="الحالة", description="عرض القنوات المفعلة")
async def bot_status(interaction: discord.Interaction):
    enabled = []
    for cid, active in active_channels.items():
        if active:
            ch = bot.get_channel(int(cid))
            if ch:
                enabled.append(f"• {ch.mention}")
    
    msg = f"**✅ القنوات المفعلة:**\n" + ("\n".join(enabled) if enabled else "لا يوجد")
    await interaction.response.send_message(msg, ephemeral=True)

# ==================== التشغيل ====================
if __name__ == "__main__":
    bot.run(TOKEN)