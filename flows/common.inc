# fetcher task ( to get timeseries data from a source )
common-fetcher.profile = io_bound
common-fetcher.cmd = "python $(bin_dir)/fetcher.py fetch --from %{TIME_FROM} --to %{TIME_TO} %{SOURCE} %{ID} %O0"

#minfilter task ( to filter timeseries data into a smoothed version )
common-minfilter.profile = cpu_bound
common-minfilter.cmd = "env LD_LIBRARY_PATH=$(cpp_bin) $(cpp_bin)/fast_filter -csvin %I0 -csvout %O0 -outprec 12 -intr %{SOURCE.intr} -invr %{SOURCE.invr}"
