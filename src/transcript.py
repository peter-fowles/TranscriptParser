import re
from datetime import datetime, timedelta
import sys
from collections.abc import Callable
from pathlib import Path

class Transcript:    
    def __init__(self):
        self.__lines: list['TranscriptLine'] = []
        self.__speakers: set[str] = set()
        self.__silence_intervals: list[timedelta] = []
        self.__total_speaking_time: timedelta = timedelta()
        self.__total_silence: timedelta = timedelta()

    @classmethod
    def parse_transcript(cls, path: Path) -> 'Transcript':
        obj = cls()
        with open(path, 'r') as t:
            lines = t.read().strip().split('\n\n')
            if lines[0] == 'WEBVTT':
                lines = lines[1:]
            for line in lines:
                obj.__add_item(TranscriptLine.parse_line(line))
        return obj

    def __add_item(self, item: 'TranscriptLine') -> None:
        if self.__lines:
            silence = item - self.__lines[-1]
            self.__total_silence += silence
            self.__silence_intervals.append(silence)
        self.__lines.append(item)
        self.__speakers.add(item.get_speaker())
        self.__total_speaking_time += item.get_duration()

    def __str__(self) -> str:
        return '\n\n'.join([str(i + 1) + '\n' + str(self.__lines[i]) for i in range(len(self.__lines))])
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False
        return self.num_lines() == other.num_lines() \
            and all([self.get_lines()[i] == other.get_lines()[i] for i in range(self.num_lines())])
    
    def num_lines(self):
        return len(self.__lines)
    
    def show_speakers(self) -> str:
        return '\n'.join(list(self.__speakers))
    
    def map_speakers(self, speaker_map: dict[str,str]) -> 'Transcript':
        mapped = Transcript()
        for line in self.__lines:
            if line.get_speaker() in speaker_map:
                mapped.__add_item(TranscriptLine.create(start_time=line.get_start_time(), 
                                                 end_time=line.get_end_time(), 
                                                 speaker=speaker_map[line.get_speaker()], 
                                                 text=line.get_text()))
            else:
                mapped.__add_item(line)
        return mapped

    def alternate_speakers(self, speaker_names: list[str]) -> 'Transcript':
        alternated = Transcript()
        for i in range(len(self.__lines)):
            line = self.__lines[i]
            alternated.__add_item(TranscriptLine.create(start_time=line.get_start_time(), 
                                                 end_time=line.get_end_time(), 
                                                 speaker=speaker_names[i % len(speaker_names)], 
                                                 text=line.get_text()))
        return alternated
    
    def merge(self, merge_predicate: Callable[['TranscriptLine', 'TranscriptLine'], bool]) -> 'Transcript':
        """
        merges lines of a transcript on a predicate condition

        args:
            merge_predicate: a Callable that takes an int value i such that 0 <= i < transcript.num_lines() - 1 and returns a bool
        """
        merged = Transcript()
        next_merged_line = self.__lines[0]
        for curr_line in self.__lines[1:]:
            if merge_predicate(next_merged_line, curr_line):
                next_merged_line = TranscriptLine.create(
                    next_merged_line.get_start_time(), 
                    curr_line.get_end_time(), 
                    next_merged_line.get_speaker(),
                    next_merged_line.get_text() + ' ' + curr_line.get_text())
            else:
                merged.__add_item(next_merged_line)
                next_merged_line = curr_line
        merged.__add_item(next_merged_line)
        return merged
    
    @staticmethod
    def __same_speaker(line1: 'TranscriptLine', line2: 'TranscriptLine') -> bool:
        return line1.get_speaker() == line2.get_speaker()
    
    @staticmethod
    def __longer_silence(line1: 'TranscriptLine', line2: 'TranscriptLine', interval: timedelta) -> bool:
        return line2 - line1 >= interval
    
    def merge_by_speaker(self, silence_interval: timedelta|None=None) -> 'Transcript':
        if len(self.__speakers) < 2:
            if input(f'WARNING: There is only one speaker in this transcript! Are you sure you want to continue? (y/n): ').strip().lower() == 'n':
                return self
        return self.merge(self.__same_speaker)
    
    def merge_by_silence_interval(self, interval:timedelta|None=None, ignore_speakers=False) -> 'Transcript':
        if interval is None:
            interval = self.median_silence()
        def pred(line1: 'TranscriptLine', line2: 'TranscriptLine') -> bool:
            return self.__longer_silence(line1, line2, interval)
        if not ignore_speakers:
            pred = pred and self.__same_speaker
        return self.merge(pred)
    
    def get_silence_intervals(self, sort: bool=False) -> list[timedelta]:
        if sort:
            return sorted(self.__silence_intervals)
        return self.__silence_intervals

    def total_time(self) -> timedelta:
        return self.__lines[-1].get_end_time()
    
    def total_speaking_time(self) -> timedelta:
        return self.__total_speaking_time
    
    def total_silence(self) -> timedelta:
        return self.__total_silence
    
    def avg_silence(self) -> timedelta:
        return self.total_silence() / (len(self.__lines) - 1)
    
    def median_silence(self) -> timedelta:
        silence_intervals = self.get_silence_intervals(sort=True)
        return silence_intervals[len(silence_intervals) // 2]
    
    def avg_speaking_time(self) -> timedelta:
        return self.total_speaking_time() / len(self.__lines)
    
    def median_speaking_time(self) -> timedelta:
        return sorted(self.__lines, key=lambda x: x.get_duration())[len(self.__lines) // 2].get_duration()
    
    def std_silence(self) -> timedelta:
        total_seconds = 0
        mean = self.avg_silence()
        for interval in self.get_silence_intervals():
            total_seconds += (interval - mean).total_seconds() ** 2
        std_seconds = (total_seconds / (len(self.__lines) - 1)) ** 0.5
        return timedelta(seconds=std_seconds)
    
    def std_speaking_time(self) -> timedelta:
        return timedelta()
    
    def get_lines(self) -> list['TranscriptLine']:
        return self.__lines
    
    def consolidate(self) -> str:
        return '\n\n'.join([f'{line.get_speaker()}: {line.get_text()}' for line in self.__lines])

class TranscriptLine:
    def __init__(self):
        self.__start_time = timedelta()
        self.__end_time = timedelta()
        self.__speaker = ''
        self.__text = ''

    @classmethod
    def create(cls, start_time: timedelta, end_time: timedelta, speaker: str, text: str) -> 'TranscriptLine':
        """ 
        creates a transcript line with raw data
        """
        obj = cls()
        obj.__start_time = start_time
        obj.__end_time = end_time
        obj.__speaker = speaker
        obj.__text = text
        return obj        

    @classmethod
    def parse_line(cls, line: str) -> 'TranscriptLine':
        """
        parses a vtt transcript line

        Expected Input Format:

        <line_number>
        <start_time> --> <end_time>
        <speaker>: <text>
        """
        line_pattern = \
            r'(?P<line_num>[1-9][0-9]*)\n' \
            r'(?P<start_time>[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}) --> (?P<end_time>[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3})\n' \
            r'(?P<speaker>.+): (?P<text>.+)$'
        result = re.fullmatch(line_pattern, line)
        if result is None:
            raise ValueError(f'Line is not a valid vtt transcript line: \n{line}')
        obj = cls()
        obj.__start_time = obj.__parse_time(result.groupdict()['start_time'])
        obj.__end_time = obj.__parse_time(result.groupdict()['end_time'])
        obj.__speaker, obj.__text = result.groupdict()['speaker'], result.groupdict()['text']
        return obj
    
    def set_speaker(self, new_name) -> None:
        self.__speaker = new_name

    def __parse_time(self, time: str) -> timedelta:
        fmt = "%H:%M:%S.%f" 
        dt = datetime.strptime(time, fmt)
        result = timedelta(
            hours=dt.hour,
            minutes=dt.minute,
            seconds=dt.second,
            microseconds=dt.microsecond
        )
        return result
    
    def get_start_time(self) -> timedelta:
        return self.__start_time
    
    def get_end_time(self) -> timedelta:
        return self.__end_time
    
    def get_duration(self) -> timedelta:
        return self.__end_time - self.__start_time
    
    def get_speaker(self) -> str:
        return self.__speaker
    
    def get_text(self) -> str:
        return self.__text
    
    def __add__(self, other: 'TranscriptLine') -> 'TranscriptLine':
        result = TranscriptLine()
        result.__start_time = self.__start_time
        result.__end_time = other.__end_time
        result.__speaker = self.__speaker
        result.__text = self.__text + ' ' + other.__text
        return result

    def __sub__(self, other) -> timedelta:
        return self.get_start_time() - other.get_end_time()
    
    def __str__(self):
        rounded_start = str(self.__start_time).split(':')
        for i in range(len(rounded_start) - 1):
            rounded_start[i] = format(int(rounded_start[i]), '02d')
        rounded_start[-1] = format(float(rounded_start[-1]), '06.3f')
        rounded_start = ':'.join(rounded_start)
        rounded_end = str(self.__end_time).split(':')
        for i in range(len(rounded_end) - 1):
            rounded_end[i] = format(int(rounded_end[i]), '02d')
        rounded_end[-1] = format(float(rounded_end[-1]), '06.3f')
        rounded_end = ':'.join(rounded_end)
        return f'{rounded_start} --> {rounded_end}\n'\
            f'{self.__speaker}: {self.__text}'
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TranscriptLine):
            return False
        return self.get_start_time() == other.get_start_time() \
            and self.get_end_time() == other.get_end_time() \
            and self.get_speaker() == other.get_speaker() \
            and self.get_text() == other.get_text()

if __name__ == '__main__':
    t = Transcript.parse_transcript(sys.argv[1])
    print(str(t.merge_by_silence_interval(timedelta(), ignore_speakers=True)))