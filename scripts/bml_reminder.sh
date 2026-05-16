#!/bin/bash
python3 ~/.openclaw/skills/claw-group-speaker/scripts/dx_send_card.py \
  --client-id a7e1759a40 \
  --client-secret 42fbc7124ccb412fbe6896322866388c \
  --template-id 46518 \
  --card-audience 873b144915 \
  --gid 70187819904 \
  --variable '{"at_highlight":"","cover_img":"","content":"**📢 BML提醒：检核销售LOSE门店是否全部提交！**"}' \
  --abstract "BML提醒"
