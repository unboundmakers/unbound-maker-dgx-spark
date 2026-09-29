#!/bin/sh
# A non-GPU child that deliberately ignores STOP to exercise the supervisor.
printf '%s\n' "$$" > "$3/child.pid"
exec sleep 60
