#!/usr/bin/env bash
# 夜间收尾：等渲染跑完 → 补渲缺帧 → 调色/剪辑/混音出 r2 → 等其它 Blender 任务 →（ALLOW_SHUTDOWN=1 时）关机
# Windows / Git Bash 专用（用 powershell 查进程）。PROJECT_TAG=命令行里能识别本项目的字符串
cd "$(dirname "$0")"
LOG=renders/night_log.txt
log(){ echo "$(date '+%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
# running <exe-name> <cmdline-pattern>: filters by process name, so the query never counts itself
running(){ powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"name='$1'\" | Where-Object { \$_.CommandLine -like '*$2*' }).Count" | tr -d '\r'; }
declare -A NEED=([S1]=96 [S2]=144 [S3]=120 [S4]=120 [S5]=120 [S6]=120 [S7]=96 [S8]=144)

log "night.sh started; waiting for render_all.sh"
TASKOUT="${TASKOUT:-}"
idle=0
while true; do
  if [ -n "$TASKOUT" ] && grep -q "done S2" "$TASKOUT" 2>/dev/null; then break; fi
  if [ "$(running blender.exe "${PROJECT_TAG:-westlake-3d}")" -eq 0 ]; then idle=$((idle+1)); else idle=0; fi
  [ "$idle" -ge 10 ] && break          # no render of this project for 10 min -> loop is over (or died)
  sleep 60
done
log "render loop finished"

for attempt in 1 2; do
  missing=""
  for S in S1 S2 S3 S4 S5 S6 S7 S8; do
    n=$(ls renders/doc/$S/f_*.png 2>/dev/null | wc -l)
    [ "$n" -lt "${NEED[$S]}" ] && missing="$missing $S"
  done
  [ -z "$missing" ] && break
  log "attempt $attempt: re-rendering incomplete shots:$missing"
  SHOTS="$missing" ./render_all.sh >> "$LOG" 2>&1
done

if [ -z "$missing" ]; then
  log "all 960 frames present; assembling r2"
  if VER=r2 ./assemble.sh >> "$LOG" 2>&1; then log "ASSEMBLE OK"; else log "ASSEMBLE FAILED"; fi
else
  log "still missing:$missing — skipping assembly"
fi

# 用户另一个项目的 Blender 渲染也让它跑完（最多再等 3 小时）
for i in $(seq 1 180); do
  [ "$(running blender.exe blender)" -eq 0 ] && break
  sleep 60
done
log "other Blender jobs: $(running blender.exe blender) still running (gave up waiting or done)"
# 关机必须用户明确授权：ALLOW_SHUTDOWN=1 ./night.sh
if [ "${ALLOW_SHUTDOWN:-0}" = "1" ]; then
  log "scheduling shutdown in 10 minutes"
  shutdown //s //t 600 //c "Render finished - shutting down in 10 min (cancel: shutdown /a)"
else
  log "done; ALLOW_SHUTDOWN not set, leaving the machine on"
fi
