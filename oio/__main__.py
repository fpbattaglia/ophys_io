#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import warnings
import os.path as op
from oio import util
from oio.conversion import continuous_to_dat


def main(cli_args=None):
    # Command line interface
    if cli_args is None:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("target", nargs='*',
                            help="""Path/list of paths to directories containing raw .continuous data OR path
                                    to .session definition file. Listing multiple files will result in data sets
                                    being concatenated in listed order.""")

        channel_group = parser.add_mutually_exclusive_group()
        channel_group.add_argument("-c", "--channel-count", type=int,
                                   help="Number of consecutive channels, 1-based index. E.g. 64: Channels 1:64")
        channel_group.add_argument("-C", "--channel-list", nargs='*', type=int,
                                   help="List of channels in order they are to be merged.")
        channel_group.add_argument("-l", "--layout",
                                   help="Path to klusta .probe file.")

        parser.add_argument("-D", "--dead-channels", nargs='*', type=int,
                            help="List of dead channels. If flag set, these will be set to zero.")
        parser.add_argument("-S", "--split-groups", action="store_false",
                            help="Split channel groups into separate files.")
        parser.add_argument("-n", "--proc-node", help="Processor node id", type=int, default=100)
        parser.add_argument("-p", "--params", help="Path to .params file.")
        parser.add_argument("-o", "--output", default=None, help="Output file path. Name of target if none given.")
        parser.add_argument("-L", "--limit-dur", help="Maximum  duration of recording (s)")
        parser.add_argument("--chunk-records", default=10000, type=int,
                            help="Number of records (2 kiB/channel) to read at a time. Increase to speed up, reduce to"
                                 "deal with memory limitations. Default: ~20 MiB/channel")
        parser.add_argument("--remove-trailing-zeros", action='store_true')
        parser.add_argument("--zero-dead-channels", action='store_true')
        cli_args = parser.parse_args()

    if cli_args.remove_trailing_zeros:
        raise NotImplementedError("Can't remove trailing zeros just yet.")
    if cli_args.split_groups:
        # i.e. use the -S flag pretty please and fix this later. Some day. Mayhaps-ish.
        raise NotImplementedError("Explicit channel group merging not supported. Defaulting to split groups.")

    # Set up channel layout (channels, references, dead channels) from command line inputs or layout file
    dead_channels = cli_args.dead_channels if cli_args.dead_channels is not None else []
    if cli_args.channel_count is not None:
        channel_groups = {0: {'channels': list(range(1, cli_args.channel_count + 1))}}
    elif cli_args.channel_list is not None:
        channel_groups = {0: {'channels': cli_args.channel_list}}
    elif cli_args.layout is not None:
        layout = util.run_prb(cli_args.layout)
        channel_groups = layout['channel_groups']
        dead_channels = layout['dead_channels'] if 'dead_channels' in layout else []
    else:
        warnings.warn('No channels given, using all found in target directory.')
        raise NotImplementedError('Grabbing all channels from file names not done yet. Sorry.')

    # involved file names
    if cli_args.output is None:
        out_path, out_file, out_ext = '', op.basename(op.splitext(cli_args.target[0])[0]), "dat"
    else:
        out_path, out_file = op.split(op.expanduser(cli_args.output))
        if out_file == '':
            out_file = op.basename(cli_args.target[0])
            out_ext = "dat"
        else:
            out_ext = op.splitext(out_file)

    # indicate when more than one source was merged into the .dat file
    out_file += "+{}files".format(len(cli_args.target) - 1) if len(cli_args.target) > 1 else ''

    for cg_id, channel_group in channel_groups.items():
        crs = util.fmt_channel_ranges(channel_group['channels'])
        output = "{outfile}--cg({cg_id:02})_ch[{crs}].{ext}".format(outfile=out_file, ext=out_ext,
                                                                    cg_id=cg_id, crs=crs)
        output_path = op.join(out_path, output)

        for append_dat, input_dir in enumerate(cli_args.target):
            print("<-- Input: {}\n--> Output: {}".format(input_dir, output_path))
            print(channel_group, dead_channels, cli_args.proc_node)
            continuous_to_dat(input_path=op.expanduser(input_dir),
                              output_path=output_path,
                              channel_group=channel_group,
                              dead_channels=dead_channels,
                              proc_node=cli_args.proc_node,
                              append=bool(append_dat),
                              chunk_records=int(cli_args.chunk_records),
                              limit_dur=cli_args.limit_dur)

if __name__ == "__main__":
    main()