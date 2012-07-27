#!/usr/bin/perl -w

if (@ARGV == 0) {
    print "Usage: csv_merge.pl <from time> <to time> <output CSV> <input CSV files .... >\n";
} else {
    $tfrom = shift(@ARGV);
    $tto = shift(@ARGV);
    $ofile = shift(@ARGV);
    @ifiles = @ARGV;
    @ifilehandles = ();
    @ilines = ();
    @ftimes = ();
    @fvals = ();
    for $ifile (@ifiles) {
        local *FILE;
        open(FILE,"<$ifile") || die "Cannot open $ifile";
        push(@ifilehandles,*FILE);
        $ln = readline(FILE);
        push(@ilines,$ln);
        push(@ftimes,0);
        push(@fvals,0);
    }
    
    open(FOUT,">$ofile") || die "Cannot open $ofile";
    
    for($t=$tfrom;$t<=$tto;) {
       for($c = 0; $c < @ifiles; $c++) {
           while(1) {
            $com = index($ilines[$c],',');
            $ltemp = $ilines[$c];
            if ($com == -1) {
                if ( eof($ifilehandles[$c])) {
                    $ftimes[$c] = 1e99;
                    last;
                }
                $ilines[$c] = readline($ifilehandles[$c]);
            } else {
                $tcsv = substr($ltemp,0,$com);
                $vcsv = substr($ltemp,$com+1);
                #print "COMP $c $t $tcsv\n";
                if ( $tcsv < $t ) {
                    if ( eof($ifilehandles[$c])) {
                        $ftimes[$c] = 1e99;
                        last;
                    }
                    $ilines[$c] = readline($ifilehandles[$c]);
                } else {
                    $ftimes[$c] = $tcsv;
                    $fvals[$c] = $vcsv;
                    last;
                }
            }
           } 
       }
       
       $closest = 0;
       for($c = 1; $c < @ifiles; $c++) {
            if ($ftimes[$c] - $t < $ftimes[$closest] - $t ) {
                $closest = $c;
            }
       }
       if ($ftimes[$closest] == 1e99) {
            last;
       }
       
       #print "CLOSEST: $closest => $ftimes[$closest]\n";
       printf FOUT ($ftimes[$closest].','.$fvals[$closest]);
       $t = $ftimes[$closest]+0.1;
    }
    close(FOUT);
    
    for $ifh (@ifilehandles) {
        close($ifh)        
    }
}