#
# sMDT tube construction, collect data from previous week
# 
# Author: Reinhard Schwienhorst, based on DatabaseViewer example
# 2021-06-02
#

from datetime import datetime, timedelta

from sMDT import db, tube
from sMDT.data import status
import sys

# get all of the tubes in the database
database=db.db()
tubes = database.get_tubes()

totTubes=0
totGood=0
totInc=0
totBent=0

# Start date is the date when we started makign tubes for the tube PRR
StartDate=datetime(year=2020, month=8,day=14, hour=23, minute=59)
#StartDate=datetime(year=2021, month=7,day=30, hour=23, minute=59)
week = 0
TodayDate=datetime.today()


while StartDate < TodayDate:
    # counters
    TubesWeeklySwaged=0
    goodTubes=0
    incTubes=0
    bentTubes=0
    tensionFail=0
    darkFail=0
    swageFail=0
    commentFail=0
    tubesErr=0
    if(week > 0): StartDate=StartDate+timedelta(days=7)
    week +=1
    EndDate = StartDate+timedelta(days=7)


    for tube in tubes:
        #print(tube.get_ID())
        isGood = tube.status()

        #if tube.get_ID()[:3]!="MSU": print(tube.get_ID())
        #continue
        # get the swage date and start processing
        swage_date=tube.get_mfg_date()
        # skip all of the early tubes that have no date
        if swage_date == None:
            tubesErr+=1
            continue

        if swage_date < EndDate and swage_date > StartDate :
            TubesWeeklySwaged+=1
            #print(swage_date)
            if isGood == status.Status.PASS: goodTubes+=1
            elif isGood == status.Status.INCOMPLETE:
                # For incomplete tubes, check if they pass dark current
                # they may be incomplete if the second tension test is done at UMich
                #print(tube.get_ID()," is incomplete.")
                try:
                    cur = tube.dark_current.get_record().dark_current
                    #print("Tube ",tube.get_ID()," is incomplete, dark current ",cur)
                    if cur < 2.:
                        # dark current is ok, so this is a good tube!
                        goodTubes+=1
                except IndexError:
                    # no dark current, so this tube is truly incomplete
                    incTubes+=1
            elif isGood == status.Status.FAIL:
                #print(tube.get_ID())
                # check for the cause of the failure
                if tube.status_bentness() == status.Status.FAIL:
                    bentTubes+=1
                elif tube.swage.status()== status.Status.FAIL:
                    swageFail+=1 
                elif tube.tension.status()== status.Status.FAIL:
                    tensionFail+=1 
                elif tube.dark_current.status()== status.Status.FAIL:
                    darkFail+=1
                elif tube.comment_fails():
                    commentFail+=1

    print("Week from ",StartDate," to ", EndDate)
    TubesWeeklySwaged -= bentTubes
    if TubesWeeklySwaged>0:
        print("Total ",TubesWeeklySwaged," swaged, good+incomplete ",goodTubes,"+",incTubes,"=",goodTubes+incTubes,", failure rate %2.1f" % (100.-(goodTubes+incTubes)/TubesWeeklySwaged*100.))
        print("  Failure reason for",TubesWeeklySwaged-goodTubes-incTubes," tubes: Swage:",swageFail,", Tension:",tensionFail,", dark:",darkFail, ", comment:",commentFail)
        print("   Plus",bentTubes,"bent tubes")

        totTubes+=TubesWeeklySwaged
        totGood+=goodTubes
        totInc+=incTubes
        totBent+=bentTubes
    else:
        print("No tube swaged")
# end of loop over weeks
#
print("Summary:")
print("Total ",totTubes," swaged, good+incomplete ",totGood,"+",totInc,"=",totGood+totInc,", failure rate %2.1f" % (100.-(totGood+totInc)/totTubes*100.))
print("Plus ",tubesErr," tubes without a date and ",totBent,"tubes that were bent.")
sys.exit(0)
