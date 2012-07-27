#!/usr/bin/perl -w

if (@ARGV == 0) {
    print "Usage: csv_bounds.pl <input CSV file> <tscale>\n";
    print "Returns: --from <min time> --to <max time>\n";
    print "Suitable for use with run_flow.py and fetcher.py\n";
    print "e.g. fetcher.py fetch `csv_bounds.pl asdf.csv` ...\n";
    print "Optionally timescale the from and to arguments\n";
} else {
	open(FIN,"<$ARGV[0]") || die "Can't open $ARGV[0]";
	$first = 0;
	while(<FIN>) {
		$i = index($_,',');
		if ( $i != -1 ) {
			$t = substr($_,0,$i);
			if ($first == 0){
				$tmin = $t;
				$first = 1;
			}
			$tmax = $t;
		}
	}
	close(FIN);
	if (@ARGV == 2) {
		$tmin /= $ARGV[1];
		$tmax /= $ARGV[1];
	}
	print "--from $tmin --to $tmax";
}