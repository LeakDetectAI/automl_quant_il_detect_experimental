#!/bin/bash
#SBATCH -J "ILD"
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --gres=gpu:a100:1
#SBATCH -A hpc-prf-aiafs
#SBATCH -t 4-00:00:00
#SBATCH -p gpu
#SBATCH --mail-user prithag@mail.uni-paderborn.de
#SBATCH -o /scratch/hpc-prf-aiafs/prithag/clusterout/%x-%j
#SBATCH -e /scratch/hpc-prf-aiafs/prithag/clusterout/%x-%j


cd $PFS_FOLDER/automl_quant_il_detect/
ml lang
ml Python/3.9.5
ml Python/3.9.5-GCCcore-10.3.0

export PYTHONUSERBASE=$PFS_FOLDER/automl_quant_il_detect/.local
export PATH=$PFS_FOLDER/automl_quant_il_detect/.bin:$PATH
export PATH=$PFS_FOLDER/automl_quant_il_detect/.local/bin:$PATH
which python
which pip

export SCRIPT_FILE=$PFS_FOLDER/automl_quant_il_detect/cluster_script_ild.py
python $SCRIPT_FILE --cindex=$SLURM_JOB_ID --isgpu=1 --schema='leakage_detection_padding'

exit 0
~