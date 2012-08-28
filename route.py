import bart_api

class Route:
    def __init__(self, name, abbr, long_id, origin, dest, direction, number, color, holidays, stations, system):
        self.name = name
        self.abbr = abbr
        self.long_id = long_id
        self.origin = origin
        self.dest = dest
        self.direction = direction
        self.number = number
        self.color = color
        self.holidays = holidays
        self.stations = stations
        self.system = system

        self.origin_times = self.get_train_origin_times()
        self.segments = [] # Filled in when the system populates segments

    def stations_from_abbr(self, abbr):
        station_strings = abbr.split(" - ")
        return [self.system.station_for_abbr(station_abbr) for station_abbr in station_strings]

    def get_train_origin_times(self):
        return bart_api.schedule_origin_times(self.system, route_num=self.number)

    def __repr__(self):
        return "<Route: %s - %s>" % (self.abbr, self.direction)