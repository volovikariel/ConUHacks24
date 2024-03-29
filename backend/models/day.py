from datetime import datetime
import json
from models.bay import Bay
from models.car import CarType
from models.job import Job
from utils.misc import ranges_overlap
from utils.schedule import schedule


class Day:
    def __init__(
        self,
        start_time: datetime,
        end_time: datetime,
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.reserved_bays: list[Bay] = [Bay([]) for _ in range(5)]
        self.walk_in_bay_by_type = {
            CarType.compact: Bay([]),
            CarType.medium: Bay([]),
            CarType.full_size: Bay([]),
            CarType.class_1_truck: Bay([]),
            CarType.class_2_truck: Bay([]),
        }
        self.reserved_jobs = []
        self.all_jobs = []
        self.total_revenue = 0
        self.total_loss = 0
        # The following two attributes are only used in schedule.py
        self.total_revenue_to_date = 0
        self.total_loss_to_date = 0

    def add_reserved_job(self, job: Job) -> None:
        self.reserved_jobs.append(job)

    def optimize_reserved_bays(self, jobs):
        remaining_jobs = jobs
        for i in range(len(self.reserved_bays)):
            # Short circuit if no remaining jobs
            if len(remaining_jobs) == 0:
                break
            max_revenue, selected_jobs = schedule(remaining_jobs)
            self.reserved_bays[i] = Bay(selected_jobs)
            remaining_jobs = self.get_declined_reserved_jobs(jobs)
        # Cleans up after handle_same_day_reserved_job
        for job in self.get_reserved_jobs():
            job.treat_as_inf = False

    def handle_walk_in_job(self, added_job: Job) -> None:
        self.all_jobs.append(added_job)
        walk_in_bay = self.walk_in_bay_by_type[added_job.car_type]
        added_job_range = (added_job.start, added_job.finish)
        if not ranges_overlap(
            added_job_range, [(job.start, job.finish) for job in walk_in_bay.jobs]
        ):
            walk_in_bay.jobs.append(added_job)
            return
        # Otherwise check if a reserved bay has no jobs and until this job is finished
        # if so, then add it to the reserved bays
        for reserved_bay in self.reserved_bays:
            if not ranges_overlap(
                added_job_range, [(job.start, job.finish) for job in reserved_bay.jobs]
            ):
                reserved_bay.jobs.append(added_job)
                return

        # Otherwise, it's turned away
        self.update_total_revenue_and_loss()

    def handle_reserved_job(self, added_job: Job) -> None:
        self.all_jobs.append(added_job)
        self.add_reserved_job(added_job)
        self.optimize_reserved_bays(self.reserved_jobs)
        self.update_total_revenue_and_loss()

    # We have to optimize only part of the day, that after the the request time
    # As optimizing the whole day could result in some of the past being modified too, which isn't realistic
    def handle_same_day_reserved_job(self, added_job: Job) -> None:
        self.all_jobs.append(added_job)
        cutoff_jobs = []
        for job in self.get_reserved_jobs():
            # If this is a job that started before the req time but ends after the req time
            # Then we want to keep it in place, and in mind for the optimization
            # To do this, we simply make its value infinite, so that the optimization always picks it
            if job.start < added_job.req_time and job.finish > added_job.req_time:
                job.treat_as_inf = True
                cutoff_jobs.append(job)
            if job.start >= added_job.req_time:
                cutoff_jobs.append(job)

        cutoff_jobs.append(added_job)
        self.optimize_reserved_bays(cutoff_jobs)
        self.update_total_revenue_and_loss()

    def get_declined_reserved_jobs(self, jobs) -> list[Job]:
        return [job for job in jobs if job not in self.get_reserved_jobs()]

    def get_reserved_jobs(self) -> list[Job]:
        reserved_jobs = []
        for reserved_bay in self.reserved_bays:
            reserved_jobs.extend(reserved_bay.jobs)
        return reserved_jobs

    def get_walk_in_jobs(self) -> list[Job]:
        walk_in_jobs = []
        for walk_in_bay in self.walk_in_bay_by_type.values():
            walk_in_jobs.extend(walk_in_bay.jobs)
        return walk_in_jobs

    def get_selected_jobs(self) -> list[Job]:
        return self.get_reserved_jobs() + self.get_walk_in_jobs()

    def get_declined_jobs(self) -> list[Job]:
        return [job for job in self.all_jobs if job not in self.get_selected_jobs()]

    def update_total_revenue_and_loss(self) -> None:
        total_revenue = 0
        for job in self.get_selected_jobs():
            total_revenue += job.revenue
        self.total_revenue = total_revenue

        total_loss = 0
        for job in self.get_declined_jobs():
            total_loss += job.revenue
        self.total_loss = total_loss

    def __str__(self) -> str:
        string = ""
        if len(self.get_reserved_jobs()) > 0:
            for bay_idx, bay in enumerate(self.reserved_bays):
                # It's 0 indexed so add 1
                string += f"Reserved bay {bay_idx + 1}: {bay}\n"
        if len(self.get_walk_in_jobs()) > 0:
            for car_type, bay in self.walk_in_bay_by_type.items():
                string += f"Walk-in bay for {car_type.value}: {bay}\n"
        return string

    def as_dict(self):
        reserved_bays = [bay.as_dict() for bay in self.reserved_bays]
        walk_in_bays = [bay.as_dict() for bay in self.walk_in_bay_by_type.values()]
        all_bays = reserved_bays + walk_in_bays
        return {
            "bays": all_bays,
            "selected_jobs": [job.as_dict() for job in self.get_selected_jobs()],
            "declined_jobs": [job.as_dict() for job in self.get_declined_jobs()],
        }

    def as_json(self):
        return json.dumps(self.as_dict(), indent=4)
