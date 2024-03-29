from datetime import datetime, timedelta
import json
from models.day import Day
from models.job import Job
from utils.csv import to_csv_date_str


class Schedule:
    def __init__(self, start_date: datetime, end_date: datetime):
        self.days: list[Day] = []

        current_date = start_date
        while current_date <= end_date:
            self.days.append(
                Day(
                    start_time=current_date + timedelta(hours=7),  # 7am
                    end_time=current_date + timedelta(hours=7 + 12),  # 7pm
                )
            )
            current_date += timedelta(days=1)

    def add_job(self, job: Job) -> None:
        day_idx = (
            job.start.timetuple().tm_yday - self.days[0].start_time.timetuple().tm_yday
        )
        # Make sure the jobs are within the day's working hours (7am to 7pm)
        if (
            job.start < self.days[day_idx].start_time
            or job.finish > self.days[day_idx].end_time
        ):
            return
        # It's a walk-in
        if job.req_time == job.start:
            self.days[day_idx].handle_walk_in_job(job)
        # The reservation date is the same as the job's date (but it's not a walk-in)
        elif job.req_time.timetuple().tm_yday == job.start.timetuple().tm_yday:
            self.days[day_idx].handle_same_day_reserved_job(job)
        else:
            self.days[day_idx].handle_reserved_job(job)

        # Keeping track of revenue/loss
        if day_idx == 0:
            self.days[day_idx].total_revenue_to_date = self.days[day_idx].total_revenue
            self.days[day_idx].total_loss_to_date = self.days[day_idx].total_loss
        else:
            self.days[day_idx].total_revenue_to_date = (
                self.days[day_idx - 1].total_revenue_to_date
                + self.days[day_idx].total_revenue
            )
            self.days[day_idx].total_loss_to_date = (
                self.days[day_idx - 1].total_loss_to_date
                + self.days[day_idx].total_loss
            )

    def as_dict(self):
        # return datetime string and day.as_dict object
        return {
            "days": [
                {
                    to_csv_date_str(day.start_time): {
                        "day": day.as_dict(),
                        "revenue_to_date": day.total_revenue_to_date,
                        "loss_to_date": day.total_loss_to_date,
                        "total_revenue": day.total_revenue,
                        "total_loss": day.total_loss,
                    }
                    for day in self.days
                }
            ]
        }

    def as_json(self):
        return json.dumps(self.as_dict(), indent=4)
