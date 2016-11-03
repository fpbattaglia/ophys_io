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


OUTFILE=${JOB_NAME}.o${JOB_ID}.${SGE_TASK_ID}
echo outfile $OUTFILE
mkdir -p battaglia
cd battaglia

EXPERIMENT=SocialPFC
ANIMAL=m0001
DATASET=2014-10-30_15-04-50
PROBEFILE=${ANIMAL}_16.prb
NODE=106
DURATION=10
GROUP=$(expr $SGE_TASK_ID - 1)

rsync -avh  -e ssh fpbatta@tompouce.science.ru.nl:/volume1/homes/reichler/data/${EXPERIMENT}/${ANIMAL}/${DATASET} .

cd ${DATASET}

rsync -avh  -e ssh fpbatta@tompouce.science.ru.nl:/volume1/homes/reichler/data/${EXPERIMENT}/${ANIMAL}/${PROBEFILE} .

source activate ophys

mkdir -p klusta${GROUP}
oio . -l ${PROBEFILE} --channel-groups ${GROUP} -S -n $NODE -D ${DURATION} -o klusta${GROUP}/raw.dat

cp /home/battaglia/batch_out/${OUTFILE} klusta${GROUP} 