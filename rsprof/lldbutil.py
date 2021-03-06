from inspect import isfunction
from typing import Any, Callable, List, Literal, Tuple
from lldb import (
    SBDebugger,
    SBTarget,
    SBFrame,
    SBBreakpointLocation,
    SBBreakpoint,
    SBValue
)

from rsprof.logutil import info


def import_lldb_command(lldb_debugger: SBDebugger, item):
    if isfunction(item):
        mod_n, cmd_n = item.__module__, item.__qualname__
        info(f"import command '{mod_n}.{cmd_n}'")
        lldb_debugger.HandleCommand(
            f"command script add -f {mod_n}.{cmd_n} {cmd_n}")
    else:
        for path in item.__path__:
            info(f"import module '{path}'")
            lldb_debugger.HandleCommand(f"command script import {path}")


class BreakpointManager:
    def __init__(self) -> None:
        self.breakpoint_callbacks: List[
            Tuple[
                str,
                int,
                Callable[[SBFrame, SBBreakpointLocation, Any, Any], None],
            ]
        ] = []
        self.registered_breakpoints: List[Tuple[SBTarget, List[int]]] = []

    def register_callback_regex(
        self,
        regex: str,
        callback: Callable[[SBFrame, SBBreakpointLocation, Any, Any], None],
    ):
        self.breakpoint_callbacks.append((regex, 1, callback))

    def register_callback_name(
        self,
        name: str,
        callback: Callable[[SBFrame, SBBreakpointLocation, Any, Any], None],
    ):
        self.breakpoint_callbacks.append((name, 0, callback))

    def update(self, debugger: SBDebugger):
        self.registered_breakpoints = list(
            filter(
                lambda x: debugger.GetIndexOfTarget(x[0]) != 4294967295,
                self.registered_breakpoints,
            )
        )

    def set(self, target: SBTarget):
        for t, _ in self.registered_breakpoints:
            if t == target:
                return False, None

        registered_breakpoints = []
        for (symb, stype, callback) in self.breakpoint_callbacks:
            bp: SBBreakpoint = (
                target.BreakpointCreateByName(symb)
                if stype == 0
                else target.BreakpointCreateByRegex(symb)
            )
            if len(bp.locations) != 0:
                bp.SetScriptCallbackFunction(
                    f"{callback.__module__}.{callback.__qualname__}"
                )
                bp.SetAutoContinue(True)
                registered_breakpoints.append(bp.id)

                
            else:
                target.BreakpointDelete(bp.id)

                # delete set breakpoints
                for bpid in registered_breakpoints:
                    target.BreakpointDelete(bpid)

                return True, symb
        self.registered_breakpoints.append((target, registered_breakpoints))
        return True, None

    def unset(self, target: SBTarget):
        for index, (t, ids) in enumerate(self.registered_breakpoints):
            if t == target:
                for id in ids:
                    target.BreakpointDelete(id)
                self.registered_breakpoints.pop(index)
                return True
        return False


def evaluate_expression_unsigned(frame: SBFrame, expression: str) -> int:
    return frame.EvaluateExpression(expression).GetValueAsUnsigned()


def get_function_parameter(frame: SBFrame, nargs: Tuple[Literal["s", "u"], ...]):
    ret_value: List[int] = []
    for id, s in enumerate(nargs):
        arg_value: SBValue = frame.EvaluateExpression(f"$arg{id + 1}")
        ret_value.append(arg_value.GetValueAsUnsigned() if s ==
                         "u" else arg_value.GetValueAsSigned())
    return tuple(ret_value)
