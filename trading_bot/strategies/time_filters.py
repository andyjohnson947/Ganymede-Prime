"""
Time Filter Module
Manages trading time windows for mean reversion and breakout strategies
"""

from datetime import datetime, time
from typing import Dict, Optional
from ..config import strategy_config as cfg


class TimeFilter:
    """
    Time-based trading window filter
    Determines which strategy (if any) can trade at current time
    """

    def __init__(self):
        self.enable_filters = cfg.ENABLE_TIME_FILTERS

        # Mean reversion windows
        self.mr_hours = set(cfg.MEAN_REVERSION_HOURS)
        self.mr_days = set(cfg.MEAN_REVERSION_DAYS)
        self.mr_sessions = set(cfg.MEAN_REVERSION_SESSIONS)

        # Breakout windows
        self.bo_hours = set(cfg.BREAKOUT_HOURS)
        self.bo_days = set(cfg.BREAKOUT_DAYS)
        self.bo_sessions = set(cfg.BREAKOUT_SESSIONS)

    def get_session(self, current_time: datetime) -> str:
        """
        Determine which trading session is active

        Args:
            current_time: Current datetime (UTC)

        Returns:
            Session name: 'tokyo', 'london', 'new_york', 'sydney'
        """
        hour = current_time.hour

        for session_name, session_info in cfg.TRADE_SESSIONS.items():
            start_hour = int(session_info['start'].split(':')[0])
            end_hour = int(session_info['end'].split(':')[0])

            # Handle session crossing midnight
            if start_hour > end_hour:
                if hour >= start_hour or hour < end_hour:
                    return session_name
            else:
                if start_hour <= hour < end_hour:
                    return session_name

        return 'unknown'

    def can_trade_mean_reversion(self, current_time: datetime) -> bool:
        """
        Check if mean reversion strategy can trade now

        Args:
            current_time: Current datetime (UTC)

        Returns:
            True if mean reversion can trade
        """
        if not self.enable_filters:
            return True

        hour = current_time.hour
        day = current_time.weekday()
        session = self.get_session(current_time)

        # Check hour filter
        in_hours = hour in self.mr_hours

        # Check day filter
        in_days = day in self.mr_days

        # Check session filter
        in_session = session in self.mr_sessions

        return in_hours and in_days and in_session

    def can_trade_breakout(self, current_time: datetime) -> bool:
        """
        Check if breakout strategy can trade now

        Args:
            current_time: Current datetime (UTC)

        Returns:
            True if breakout can trade
        """
        if not self.enable_filters:
            return True

        if not cfg.BREAKOUT_ENABLED:
            return False

        hour = current_time.hour
        day = current_time.weekday()
        session = self.get_session(current_time)

        # Check hour filter
        in_hours = hour in self.bo_hours

        # Check day filter
        in_days = day in self.bo_days

        # Check session filter
        in_session = session in self.bo_sessions

        return in_hours and in_days and in_session

    def get_active_strategy(self, current_time: datetime) -> Optional[str]:
        """
        Determine which strategy should be active now

        Args:
            current_time: Current datetime (UTC)

        Returns:
            'mean_reversion', 'breakout', or None
        """
        # Check mean reversion first (higher priority if both active)
        if self.can_trade_mean_reversion(current_time):
            return 'mean_reversion'

        # Then check breakout
        if self.can_trade_breakout(current_time):
            return 'breakout'

        return None

    def get_time_status(self, current_time: datetime) -> Dict:
        """
        Get comprehensive time filter status

        Args:
            current_time: Current datetime (UTC)

        Returns:
            Dict with detailed status information
        """
        hour = current_time.hour
        day = current_time.weekday()
        day_name = current_time.strftime('%A')
        session = self.get_session(current_time)

        can_mr = self.can_trade_mean_reversion(current_time)
        can_bo = self.can_trade_breakout(current_time)
        active_strategy = self.get_active_strategy(current_time)

        return {
            'current_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'hour': hour,
            'day': day,
            'day_name': day_name,
            'session': session,
            'filters_enabled': self.enable_filters,
            'can_trade_mean_reversion': can_mr,
            'can_trade_breakout': can_bo,
            'active_strategy': active_strategy,
            'mean_reversion_next_hour': self._next_hour_in(hour, self.mr_hours),
            'breakout_next_hour': self._next_hour_in(hour, self.bo_hours)
        }

    def _next_hour_in(self, current_hour: int, hour_set: set) -> Optional[int]:
        """
        Find next available hour in given set

        Args:
            current_hour: Current hour (0-23)
            hour_set: Set of valid hours

        Returns:
            Next valid hour, or None
        """
        sorted_hours = sorted(hour_set)

        for h in sorted_hours:
            if h > current_hour:
                return h

        # Return first hour of next day
        return sorted_hours[0] if sorted_hours else None

    def print_schedule(self):
        """
        Print the complete trading schedule
        """
        print("=" * 80)
        print("TRADING SCHEDULE")
        print("=" * 80)

        print("\n📊 MEAN REVERSION STRATEGY")
        print(f"   Hours: {sorted(self.mr_hours)}")
        print(f"   Days: {[self._day_name(d) for d in sorted(self.mr_days)]}")
        print(f"   Sessions: {sorted(self.mr_sessions)}")

        print("\n📈 BREAKOUT STRATEGY")
        print(f"   Enabled: {cfg.BREAKOUT_ENABLED}")
        if cfg.BREAKOUT_ENABLED:
            print(f"   Hours: {sorted(self.bo_hours)}")
            print(f"   Days: {[self._day_name(d) for d in sorted(self.bo_days)]}")
            print(f"   Sessions: {sorted(self.bo_sessions)}")

        print("\n⏰ HOURLY BREAKDOWN (UTC)")
        for hour in range(24):
            strategies = []
            if hour in self.mr_hours:
                strategies.append("MR")
            if hour in self.bo_hours and cfg.BREAKOUT_ENABLED:
                strategies.append("BO")

            if strategies:
                session = self._get_session_for_hour(hour)
                print(f"   {hour:02d}:00 - {', '.join(strategies)} ({session})")

    def _day_name(self, day_num: int) -> str:
        """Convert day number to name"""
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        return days[day_num] if 0 <= day_num < 7 else 'Unknown'

    def _get_session_for_hour(self, hour: int) -> str:
        """Get session name for given hour"""
        if 0 <= hour < 9:
            return 'Tokyo'
        elif 8 <= hour < 17:
            return 'London'
        elif 13 <= hour < 22:
            return 'NY'
        else:
            return 'Sydney'


def test_time_filters():
    """Test time filter functionality"""
    filter = TimeFilter()

    print("Testing Time Filters\n")
    filter.print_schedule()

    # Test specific times
    test_times = [
        datetime(2025, 12, 23, 5, 0),   # Monday 05:00 (MR)
        datetime(2025, 12, 23, 12, 0),  # Monday 12:00 (MR)
        datetime(2025, 12, 23, 14, 0),  # Monday 14:00 (BO)
        datetime(2025, 12, 23, 3, 0),   # Monday 03:00 (BO)
        datetime(2025, 12, 23, 20, 0),  # Monday 20:00 (None)
    ]

    print("\n" + "=" * 80)
    print("TEST SCENARIOS")
    print("=" * 80)

    for test_time in test_times:
        status = filter.get_time_status(test_time)
        print(f"\n{status['current_time']} ({status['day_name']} {status['session']})")
        print(f"  Active Strategy: {status['active_strategy']}")
        print(f"  Can MR: {status['can_trade_mean_reversion']}")
        print(f"  Can BO: {status['can_trade_breakout']}")


if __name__ == '__main__':
    test_time_filters()
