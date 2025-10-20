import argparse
from pathlib import Path
from transcript import Transcript
from datetime import timedelta
import re
import sys

class SilenceAction(argparse.Action):
    def __call__(self, parser, namespace, thresh):
        try:
            silence_arg = timedelta(seconds=float(thresh))
            setattr(namespace, self.dest, silence_arg)
        except ValueError:
            parser.error("Silence threshold must be a float (seconds)")

class MapAction(argparse.Action):
    def __call__(self, parser, namespace, pairs, option_string=None):
        map_pattern = r'([^\:]+\:[^\:]+,)*([^\:]+\:[^\:]+)'
        result = dict()
        if re.match(map_pattern, pairs) is not None:
            for pair in pairs.split(','):
                key,value = pair.split(':')
                result[key] = value
            setattr(namespace, self.dest, result)
        else:
            parser.error(f"Invalid key value pair structure (expected <key1:value1,key2:value2,...>, got {pairs})")

def run_merge(args:argparse.Namespace):
    ts = Transcript.parse_transcript(args.filepath)
    result = Transcript()
    silence_thresh = timedelta(args.silence_thresh)
    if args.merger == 'silence':
        result = ts.merge_by_silence_interval(silence_thresh, ignore_speakers=True)
    else:
        result = ts.merge_by_silence_interval(silence_thresh)
    out_file = sys.stdout
    if args.out is not None:
        out_file = open(args.out, 'w')
    print(str(result), file=out_file)

def run_map(args:argparse.Namespace):
    ts = Transcript.parse_transcript(args.filepath)
    result = ts.map_speakers(args.speakers)
    out_file = sys.stdout
    if args.out is not None:
        out_file = open(args.out, 'w')
    print(str(result), file=out_file)

def run_info(args:argparse.Namespace):
    ts = Transcript.parse_transcript(args.filepath)
    for arg, value in vars(args).items():
        if value == True:
            match arg:
                case 'num_lines':
                   print(f'num_lines: {len(ts.get_lines())}')
                case 'total_duration':
                   print(f'total_duration: {str(ts.total_time())}')
                case 'total_speaking_time':
                   print(f'total_speaking_time: {str(ts.total_speaking_time())}')
                case 'avg_speaking_time':
                   print(f'avg_speaking_time: {str(ts.avg_speaking_time())}')
                case 'med_speaking_time':
                   print(f'med_speaking_time: {str(ts.median_speaking_time())}')
                case 'total_silence':
                   print(f'total_silence: {str(ts.total_silence())}')
                case 'avg_silence':
                   print(f'avg_silence: {str(ts.avg_silence())}')
                case 'med_silence':
                   print(f'med_silence: {str(ts.median_silence())}')
                case 'speakers':
                   print(f'speakers: \n    {"\n    ".join(ts.show_speakers().split('\n'))}')

def run_pretty(args):
    ts = Transcript.parse_transcript(args.filepath)
    result = ts.consolidate()
    out_file = sys.stdout
    if args.out is not None:
        out_file = open(args.out, 'w')
    print(str(result), file=out_file)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='parses a .vtt transcript'
    )
    parser.add_argument('filepath', help='path to a .vtt transcript file', type=Path)
    subparsers = parser.add_subparsers()

    merge = subparsers.add_parser('merge', help='merge transcript lines by speaker or silence between lines.')
    merge.add_argument('--merger', choices=['speaker', 'silence'], default='speaker')
    merge.add_argument('--silence_thresh', type=float, default=0, nargs=1, help='maximum silence threshold to ignore while merging', action=SilenceAction)
    merge.add_argument('--out', required=False, help='file path to save new transcript into. If not specified, result will be printed instead.', type=Path)
    merge.set_defaults(func=run_merge)

    remap = subparsers.add_parser('remap', help='remap speaker names')
    remap.add_argument('speakers', 
                       help='set of key:value pairs separated by commas, where keys are names of original speakers and values are new names.', 
                       action=MapAction)
    remap.add_argument('--out', help='file path to save new transcript into. If not specified, result will be printed instead.', type=Path)
    remap.set_defaults(func=run_map)

    prettyprint = subparsers.add_parser('prettyprint', help='outputs neatly formatted transcript without timestamps')
    prettyprint.add_argument('--out', required=False, help='file path to save new transcript into. If not specified, result will be printed instead.', type=Path)
    prettyprint.set_defaults(func=run_pretty)

    info = subparsers.add_parser('info', help='retrieves info about the transcript')
    info.add_argument('--num_lines', help='returns number of lines in the transcript', action='store_true')
    info.add_argument('--total_duration', help='gets total transcript duration', action='store_true')
    info.add_argument('--total_speaking_time', help='gets total speaking time', action='store_true')
    info.add_argument('--avg_speaking_time', help='gets average speaking time over all transcript lines', action='store_true')
    info.add_argument('--med_speaking_time', help='gets median speaking time over all transcript lines', action='store_true')
    info.add_argument('--total_silence', help='gets total silence between transcript lines', action='store_true')
    info.add_argument('--avg_silence', help='gets average silence between transcript lines', action='store_true')
    info.add_argument('--med_silence', help='gets median silence between transcript lines', action='store_true')
    info.add_argument('--speakers', help='gets all known speakers in a transcript', action='store_true')
    info.set_defaults(func=run_info)

    args = parser.parse_args()
    args.func(args)
    