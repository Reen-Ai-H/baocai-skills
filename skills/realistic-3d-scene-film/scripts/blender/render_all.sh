#!/usr/bin/env bash
cd "$(dirname "$0")"
B="${BLENDER:-blender}"; W="$(pwd -W 2>/dev/null || pwd)"   # BLENDER=<blender 可执行文件路径>
for S in ${SHOTS:-S2 S3 S7 S8 S1 S5 S4 S6}; do
  echo "== $S $(date +%H:%M:%S)"
  "$B" -b --factory-startup -P build_westlake.py -- "$W/renders/doc" ${SPP:-32} ${RES:-75} doc $S > "renders/doc/log_$S.txt" 2>&1
  echo "   done $S $(date +%H:%M:%S) frames=$(ls renders/doc/$S 2>/dev/null | wc -l) $(grep -c Traceback renders/doc/log_$S.txt) tracebacks"
done
