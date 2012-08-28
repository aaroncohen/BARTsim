import bart_api

class Schedule:
    def __init__(self, id, effective_date, system):
        self.id = id
        self.effective_date = effective_date
        self.system = system
        self.train_origin_times = bart_api.schedule_origin_times(self.system, schedule_num=self.id)

    def get_train_origin_times(self, route):
        return bart_api.schedule_origin_times(self.system, schedule_num=self.id, route_num=route.number)