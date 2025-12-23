"""Check what time the bot sees"""
import sys
sys.path.insert(0, 'trading_bot')

from datetime import datetime
import pytz
from utils.timezone_manager import get_current_time
from strategies.time_filters import TimeFilter

print("=" * 80)
print("BOT TIMEZONE CHECK")
print("=" * 80)

# Get bot's view of current time
bot_time = get_current_time()
print(f"\n🤖 Bot's current time: {bot_time}")
print(f"   Timezone: {bot_time.tzinfo}")

# Get pure GMT
gmt_now = datetime.now(pytz.UTC)
print(f"\n🌍 Pure GMT/UTC time:  {gmt_now}")

# Get UK time
uk_tz = pytz.timezone("Europe/London")
uk_now = datetime.now(uk_tz)
print(f"\n🇬🇧 UK timezone time:  {uk_now}")
print(f"   DST active: {uk_now.dst() != pytz.UTC.localize(datetime.utcnow()).replace(tzinfo=None).replace(tzinfo=pytz.UTC).dst()}")

# Check time filters
tf = TimeFilter()
print(f"\n⚙️  BROKER_GMT_OFFSET: {tf.broker_offset} hours")

# Convert to GMT if needed
if tf.broker_offset != 0:
    gmt_from_broker = tf.broker_time_to_gmt(bot_time)
    print(f"   Converted to GMT: {gmt_from_broker}")

# Check what's tradeable
can_mr = tf.can_trade_mean_reversion(bot_time)
can_bo = tf.can_trade_breakout(bot_time)

print(f"\n📊 TRADING STATUS (Hour {bot_time.hour}):")
print(f"   Mean Reversion: {'✅ ACTIVE' if can_mr else '❌ INACTIVE'}")
print(f"   Breakout: {'✅ ACTIVE' if can_bo else '❌ INACTIVE'}")

print("\n" + "=" * 80)
print("If bot time doesn't match your actual GMT time, there's a timezone issue!")
print("=" * 80)
