# fetcher task ( to get timeseries data from a source )
fetcher.profile = io_bound
fetcher.cmd = "python $(bin_dir)/fetcher.py fetch --from %{TIME_FROM} --to %{TIME_TO} %{SOURCE} %{DEVICE} %O0"

#minfilter task ( to filter timeseries data into a smoothed version )
minfilter.profile = cpu_bound
minfilter.cmd = "env LD_LIBRARY_PATH=$(cpp_bin) $(cpp_bin)/fast_filter -csvin %I0 -csvout %O0 -outprec 12 -intr %{SOURCE.intr} -invr %{SOURCE.invr}"
