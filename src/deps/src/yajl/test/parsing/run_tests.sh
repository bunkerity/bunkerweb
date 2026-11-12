#!/bin/sh

ECHO=`which echo`

DIFF_FLAGS="-u"
case "$(uname)" in
  *W32*)
    DIFF_FLAGS="-wu"
    ;;
esac

if [ -z "$testBin" ]; then
    testBin="$1"
fi

# find test binary on both platforms.  allow the caller to force a
# particular test binary (useful for non-cmake build systems).
if [ -z "$testBin" ]; then
    testBin="../build/test/parsing/Release/yajl_test.exe"
    if [ ! -x $testBin ] ; then
        testBin="../build/test/parsing/Debug/yajl_test.exe"
        if [ ! -x $testBin ] ; then
            testBin="../build/test/parsing/yajl_test"
            if [  ! -x $testBin ] ; then
                ${ECHO} "cannot execute test binary: '$testBin'"
                exit 1;
            fi
        fi
    fi
fi

${ECHO} "using test binary: $testBin"

testBinShort=`basename $testBin`

testsSucceeded=0
testsTotal=0

for file in cases/*.json ; do
  allowComments=""
  allowGarbage=""
  allowMultiple=""
  allowPartials=""

  # if the filename starts with dc_, we disallow comments for this test
  case $(basename $file) in
    ac_*)
      allowComments="-c "
    ;;
    ag_*)
      allowGarbage="-g "
     ;;
    am_*)
     allowMultiple="-m ";
     ;;
    ap_*)
     allowPartials="-p ";
    ;;
  esac
  fileShort=`basename $file`
  testName=`echo $fileShort | sed -e 's/\.json$//'`

  ${ECHO} -n " test ($testName): "
  iter=1
  success="SUCCESS"

  # ${ECHO} -n "$testBinShort $allowPartials$allowComments$allowGarbage$allowMultiple-b $iter < $fileShort > ${fileShort}.test : "
  # parse with a read buffer size ranging from 1-31 to stress stream parsing
  while [ $iter -lt 32  ] && [ $success = "SUCCESS" ] ; do
    $testBin $allowPartials $allowComments $allowGarbage $allowMultiple -b $iter < $file > ${file}.test  2>&1
    diff ${DIFF_FLAGS} ${file}.gold ${file}.test > ${file}.out
    if [ $? -eq 0 ] ; then
      if [ $iter -eq 31 ] ; then testsSucceeded=$(( $testsSucceeded + 1 )) ; fi
    else
      success="FAILURE"
      iter=32
      ${ECHO}
      cat ${file}.out
    fi
    iter=$(( iter + 1 ))
    rm ${file}.test ${file}.out
  done

  ${ECHO} $success
  testsTotal=$(( testsTotal + 1 ))
done

${ECHO} $testsSucceeded/$testsTotal tests successful

if [ $testsSucceeded != $testsTotal ] ; then
  exit 1
fi

exit 0
