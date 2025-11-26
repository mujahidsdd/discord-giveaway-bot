import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
import os
import random
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# إعدادات البوت
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

# متغير لتتبع محاولات الاتصال
reconnect_attempts = 0
max_reconnect_delay = 300  # 5 دقائق كحد أقصى

# قاموس لحفظ الـ Giveaways النشطة
active_giveaways = {}
giveaway_id = 0

@bot.event
async def on_ready():
    global reconnect_attempts
    reconnect_attempts = 0
    print(f'{bot.user} تم تسجيل دخول البوت بنجاح')
    await bot.tree.sync()

@bot.event
async def on_error(event, *args, **kwargs):
    print(f'خطأ في {event}')
    import traceback
    traceback.print_exc()

class GiveawayButton(discord.ui.View):
    def __init__(self, giveaway_id_param: int):
        super().__init__(timeout=None)
        self.giveaway_id_param = giveaway_id_param
    
    @discord.ui.button(label="🎉 اضغط للدخول", style=discord.ButtonStyle.primary, custom_id="giveaway_join_btn")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        
        if self.giveaway_id_param not in active_giveaways:
            await interaction.followup.send("❌ هذا الـ giveaway انتهى", ephemeral=True)
            return
        
        giveaway = active_giveaways[self.giveaway_id_param]
        
        # التحقق من دخول المستخدم مسبقاً
        if interaction.user.id in giveaway['participants']:
            await interaction.followup.send("❌ أنت مسجل بالفعل في هذا السحب!", ephemeral=True)
            return
        
        # إضافة المشارك
        giveaway['participants'].add(interaction.user.id)
        new_count = len(giveaway['participants'])
        
        # تحديث عدد المشاركين في الرسالة
        try:
            channel = bot.get_channel(giveaway['channel_id'])
            if channel and isinstance(channel, (discord.TextChannel, discord.Thread)):
                message = await channel.fetch_message(giveaway['message_id'])
                
                if message.embeds:
                    embed = message.embeds[0]
                    
                    # تحديث عدد المشاركين
                    for i, field in enumerate(embed.fields):
                        if field.name == "👥 عدد المشاركين":
                            embed.set_field_at(i, name="👥 عدد المشاركين", value=str(new_count), inline=False)
                            break
                    
                    await message.edit(embed=embed, view=self)
        except Exception as e:
            print(f"خطأ في تحديث الرسالة: {e}")
        
        await interaction.followup.send(f"✅ تم تسجيلك في السحب بنجاح! المشاركون الحالي: {new_count}", ephemeral=True)

@bot.tree.command(name="giveaway", description="إنشاء giveaway جديد")
@discord.app_commands.describe(
    prize="اسم الجائزة",
    winners="عدد الفائزين (افتراضي: 1)",
    duration="مدة الـ giveaway (مثال: 1h, 30m, 2d)"
)
async def giveaway(interaction: discord.Interaction, prize: str, duration: str, winners: int = 1):
    """
    إنشاء giveaway جديد مع تحديد الجائزة والفائزين والمدة
    """
    global giveaway_id
    
    # التحقق من عدد الفائزين
    if winners < 1:
        await interaction.response.send_message("❌ عدد الفائزين يجب أن يكون 1 على الأقل", ephemeral=True)
        return
    
    # تحويل المدة إلى ثواني
    try:
        time_value = int(''.join(filter(str.isdigit, duration)))
        time_unit = ''.join(filter(str.isalpha, duration)).lower()
        
        if time_unit == 'h':
            end_time = datetime.now() + timedelta(hours=time_value)
        elif time_unit == 'm':
            end_time = datetime.now() + timedelta(minutes=time_value)
        elif time_unit == 'd':
            end_time = datetime.now() + timedelta(days=time_value)
        else:
            await interaction.response.send_message("❌ صيغة المدة غير صحيحة! استخدم: 1h, 30m, 2d", ephemeral=True)
            return
    except:
        await interaction.response.send_message("❌ صيغة المدة غير صحيحة! استخدم: 1h, 30m, 2d", ephemeral=True)
        return
    
    giveaway_id += 1
    
    # إنشاء embed جذاب للـ Giveaway
    embed = discord.Embed(
        title="🎁 **جائزة جديدة!**",
        description=f"**الجائزة:** {prize}",
        color=discord.Color.gold(),
        timestamp=end_time
    )
    embed.add_field(name="🏆 عدد الفائزين", value=str(winners), inline=True)
    embed.add_field(name="📅 وقت الانتهاء", value=f"<t:{int(end_time.timestamp())}:R>", inline=True)
    embed.add_field(name="👥 عدد المشاركين", value="0", inline=False)
    embed.add_field(name="🎯 من ينظم السحب", value=interaction.user.mention, inline=False)
    embed.set_footer(text=f"Giveaway ID: {giveaway_id} • اضغط الزر أدناه للدخول")
    
    # إرسال الـ embed مع الزر
    view = GiveawayButton(giveaway_id)
    await interaction.response.send_message(embed=embed, view=view)
    message = await interaction.original_response()
    
    # حفظ معلومات الـ giveaway
    if interaction.channel_id:
        active_giveaways[giveaway_id] = {
            'message_id': message.id,
            'channel_id': interaction.channel_id,
            'prize': prize,
            'end_time': end_time,
            'participants': set(),
            'host': interaction.user.id,
            'winners_count': winners,
            'status': 'active'
        }
    
        await interaction.followup.send(f"✅ تم إنشاء السحب بنجاح! رقم الـ ID: {giveaway_id}", ephemeral=True)
        
        # انتظار انتهاء الوقت
        asyncio.create_task(finish_giveaway(giveaway_id))

async def finish_giveaway(giv_id: int) -> None:
    """
    إنهاء الـ giveaway واختيار الفائزين
    """
    if giv_id not in active_giveaways:
        return
    
    giveaway = active_giveaways[giv_id]
    wait_time = (giveaway['end_time'] - datetime.now()).total_seconds()
    
    if wait_time > 0:
        await asyncio.sleep(wait_time)
    
    # الحصول على الرسالة
    channel = bot.get_channel(giveaway['channel_id'])
    if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread)):
        if giv_id in active_giveaways:
            del active_giveaways[giv_id]
        return
    
    try:
        message = await channel.fetch_message(giveaway['message_id'])
    except:
        if giv_id in active_giveaways:
            del active_giveaways[giv_id]
        return
    
    # الحصول على المشاركين
    participants_list = list(giveaway['participants'])
    
    # اختيار الفائزين
    if participants_list:
        winners_count = min(giveaway['winners_count'], len(participants_list))
        winners = random.sample(participants_list, winners_count)
        
        # إنشاء قائمة الفائزين
        winners_text = "\n".join([f"🏆 <@{winner_id}>" for winner_id in winners])
        
        embed = discord.Embed(
            title="🎊 **انتهى السحب!**",
            description=f"**الجائزة:** {giveaway['prize']}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="🏆 الفائزين", value=winners_text, inline=False)
        embed.add_field(name="👥 إجمالي المشاركين", value=str(len(participants_list)), inline=True)
        embed.add_field(name="🎯 عدد الفائزين", value=str(winners_count), inline=True)
        embed.set_footer(text=f"Giveaway ID: {giv_id}")
        
        await message.edit(embed=embed, view=None)
        
        # إرسال رسالة تهنئة في القناة
        winners_mentions = ", ".join([f"<@{winner_id}>" for winner_id in winners])
        await channel.send(f"🎉 **تهانينا للفائزين!** {winners_mentions}\nلقد فزتم بـ **{giveaway['prize']}**! 🎁")
        
        # إرسال رسالة خاصة للفائزين
        for winner_id in winners:
            try:
                user = await bot.fetch_user(winner_id)
                dm_embed = discord.Embed(
                    title="🎉 تهانينا!",
                    description=f"لقد فزت بـ **{giveaway['prize']}**!",
                    color=discord.Color.gold()
                )
                dm_embed.add_field(name="📍 القناة", value=f"<#{giveaway['channel_id']}>", inline=False)
                await user.send(embed=dm_embed)
            except:
                pass
    else:
        embed = discord.Embed(
            title="❌ **انتهى السحب!**",
            description="للأسف لم يشارك أحد في هذا السحب 😢",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="🎯 الجائزة", value=giveaway['prize'], inline=False)
        embed.set_footer(text=f"Giveaway ID: {giv_id}")
        await message.edit(embed=embed, view=None)
    
    # تحديث الحالة وحذف من القاموس
    giveaway['status'] = 'finished'
    await asyncio.sleep(3600)  # احتفظ بالبيانات لمدة ساعة
    if giv_id in active_giveaways:
        del active_giveaways[giv_id]

@bot.tree.command(name="giveaway_stats", description="عرض إحصائيات السحب")
@discord.app_commands.describe(
    giveaway_id="رقم الـ giveaway"
)
async def giveaway_stats(interaction: discord.Interaction, giveaway_id: int):
    """
    عرض إحصائيات السحب والمشاركين
    """
    if giveaway_id not in active_giveaways:
        await interaction.response.send_message("❌ لم يتم العثور على السحب", ephemeral=True)
        return
    
    giveaway = active_giveaways[giveaway_id]
    remaining_time = (giveaway['end_time'] - datetime.now()).total_seconds()
    
    embed = discord.Embed(
        title=f"📊 إحصائيات السحب #{giveaway_id}",
        description=f"**الجائزة:** {giveaway['prize']}",
        color=discord.Color.blue()
    )
    embed.add_field(name="👥 عدد المشاركين", value=str(len(giveaway['participants'])), inline=True)
    embed.add_field(name="🏆 عدد الفائزين", value=str(giveaway['winners_count']), inline=True)
    embed.add_field(name="⏱️ الوقت المتبقي", value=f"<t:{int(giveaway['end_time'].timestamp())}:R>", inline=False)
    embed.add_field(name="🎯 منظم السحب", value=f"<@{giveaway['host']}>", inline=False)
    embed.add_field(name="📈 الحالة", value="🟢 نشط" if giveaway['status'] == 'active' else "✅ منتهي", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="giveaway_participants", description="عرض قائمة المشاركين")
@discord.app_commands.describe(
    giveaway_id="رقم الـ giveaway"
)
async def giveaway_participants(interaction: discord.Interaction, giveaway_id: int):
    """
    عرض قائمة المشاركين في السحب
    """
    if giveaway_id not in active_giveaways:
        await interaction.response.send_message("❌ لم يتم العثور على السحب", ephemeral=True)
        return
    
    giveaway = active_giveaways[giveaway_id]
    participants = list(giveaway['participants'])
    
    if not participants:
        embed = discord.Embed(
            title=f"📋 المشاركين في السحب #{giveaway_id}",
            description="لم يشارك أحد بعد 😢",
            color=discord.Color.red()
        )
    else:
        # تقسيم المشاركين إلى أجزاء لتجنب حد الأحرف
        chunks = [participants[i:i+20] for i in range(0, len(participants), 20)]
        
        embed = discord.Embed(
            title=f"📋 المشاركين في السحب #{giveaway_id}",
            description=f"**الإجمالي:** {len(participants)} مشارك",
            color=discord.Color.blue()
        )
        
        for idx, chunk in enumerate(chunks):
            participants_text = "\n".join([f"• <@{p}>" for p in chunk])
            embed.add_field(
                name=f"المشاركين ({idx+1}/{len(chunks)})",
                value=participants_text,
                inline=False
            )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="giveaway_end", description="إنهاء السحب مبكراً")
@discord.app_commands.describe(
    giveaway_id="رقم الـ giveaway"
)
async def giveaway_end(interaction: discord.Interaction, giveaway_id: int):
    """
    إنهاء السحب مبكراً (فقط للمنظم)
    """
    if giveaway_id not in active_giveaways:
        await interaction.response.send_message("❌ لم يتم العثور على السحب", ephemeral=True)
        return
    
    giveaway = active_giveaways[giveaway_id]
    
    # التحقق من أن المستخدم هو منظم السحب
    if giveaway['host'] != interaction.user.id:
        await interaction.response.send_message("❌ فقط منظم السحب يمكنه إنهاءه مبكراً", ephemeral=True)
        return
    
    await interaction.response.send_message("✅ جاري إنهاء السحب...", ephemeral=True)
    
    # تعديل وقت الانتهاء ليكون الآن
    giveaway['end_time'] = datetime.now()
    
    # استدعاء دالة الانتهاء
    asyncio.create_task(finish_giveaway(giveaway_id))

# تشغيل البوت مع معالجة الأخطاء
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if not TOKEN:
    print("❌ لم يتم العثور على DISCORD_BOT_TOKEN في متغيرات البيئة")
    exit(1)

async def run_bot():
    global reconnect_attempts
    try:
        await bot.start(TOKEN)
    except (discord.errors.HTTPException, OSError) as e:
        reconnect_attempts += 1
        delay = min(2 ** reconnect_attempts, max_reconnect_delay)
        print(f"❌ خطأ في الاتصال: {e}")
        print(f"⏳ إعادة المحاولة بعد {delay} ثانية...")
        await asyncio.sleep(delay)
        await run_bot()
    except Exception as e:
        print(f"❌ خطأ غير متوقع: {e}")
        await asyncio.sleep(10)
        await run_bot()

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\n🛑 إيقاف البوت")
    except Exception as e:
        print(f"❌ خطأ حرج: {e}")
        exit(1)
