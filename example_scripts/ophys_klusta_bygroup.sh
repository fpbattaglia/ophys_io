#!/bin/bash
#
# below you have to specify the range of channel groups *plus one*
#$ -t 1-4
#$ -cwd
#$ -j y
#$ -S /bin/bash
#$ -o /home/battaglia/batch_out
#

export PATH=/home/battaglia/anaconda3/bin::$PATH
echo 
HOST=`hostname`
echo host $HOST
#WORKDIR=/peones/${HOST}
WORKDIR=/local
echo $WORKDIR
cd $WORKDIR
SHARE=$USER
REMOTE_SHARE=fpbatta@tompouce.science.ru.nl:/volume1/homes/reichler/data
OUTFILE=${JOB_NAME}.o${JOB_ID}.${SGE_TASK_ID}
echo outfile $OUTFILE
mkdir -p $SHARE
cd $SHARE

EXPERIMENT=SocialPFC
ANIMAL=m0001
DATASET=2014-10-30_15-04-50
PROBEFILE=${ANIMAL}_16.prb
NODE=106
DURATION=10
if [ -z $SGE_TASK_ID ] ; then
	GROUP=4
else
	GROUP=$(expr $SGE_TASK_ID - 1)
fi


mkdir -p ${DATASET}
cd ${DATASET}

rsync -avh  -e ssh ${REMOTE_SHARE}/${EXPERIMENT}/${ANIMAL}/${PROBEFILE} .

source activate ophys
get_needed_channels --node=106 m0001_16.prb 4 > chans.txt
rsync --files-from=chans.txt  -avh  -e ssh ${REMOTE_SHARE}/${EXPERIMENT}/${ANIMAL}/${DATASET} .

mkdir -p klusta${GROUP}
oio . -l ${PROBEFILE} --channel-groups ${GROUP} -S -n $NODE -D ${DURATION} -o klusta${GROUP}/raw.dat

cp /home/battaglia/batch_out/${OUTFILE} klusta${GROUP} 