#!/bin/bash
#SBATCH -J "MIEstimation"
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH -A hpc-prf-autosca
#SBATCH -t 3-00:00:00
#SBATCH -p largemem
#SBATCH -o /scratch/hpc-prf-autosca/prithag/clusterout/%x-%j
#SBATCH -e /scratch/hpc-prf-autosca/prithag/clusterout/%x-%j

cd $PFS_FOLDER/information-leakage-techniques/
module reset
ml lang
ml Python/3.9.5
source ~/.bashrc
which python
which pip

export SCRIPT_FILE=$PFS_FOLDER/information-leakage-techniques/cluster_script.py
python $SCRIPT_FILE --cindex=$SLURM_JOB_ID --isgpu=0 --schema=$1

exit 0
~