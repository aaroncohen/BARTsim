class Station:
    def __init__(self, abbr, name, lat, lng, segments, system):
        self.abbr = abbr
        self.name = name
        self.lat = lat
        self.lng = lng
        self.segments = segments
        self.trains = None
        self.system = system

    def add_containing_segment(self, segment):
        if not segment in self.segments:
            assert(segment.n_station == self or segment.s_station == self)
            self.segments.append(segment)

    def segment_to_station(self, other_station):
        segment_to_station = None
        for segment in self.segments:
            if segment.n_station == other_station or segment.s_station == other_station:
                segment_to_station = segment
        return segment_to_station

    def __repr__(self):
        return "<Station: %s>" % self.name