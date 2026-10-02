"""Option parsing for commands, with the error wording of the real GNU tools."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Opts:
    flags: set[str] = field(default_factory=set)
    values: dict[str, list[str]] = field(default_factory=dict)
    rest: list[str] = field(default_factory=list)

    def has(self, *names: str) -> bool:
        return any(n in self.flags for n in names)

    def get(self, name: str, default: str | None = None) -> str | None:
        vals = self.values.get(name)
        return vals[-1] if vals else default

    def all(self, name: str) -> list[str]:
        return self.values.get(name, [])

    def num(self, name: str, default: int | None = None) -> int | None:
        v = self.get(name)
        if v is None:
            return default
        try:
            return int(v)
        except ValueError:
            return default


def parse(ctx, args: list[str], short: str = "", with_arg: str = "", long: dict[str, str] | None = None, long_arg: dict[str, str] | None = None,
          numeric: str = "", stop_at_positional: bool = False) -> Opts | None:
    """Parse GNU-style options.

    short: boolean short flags ("la" for -l -a); with_arg: short options that take a value (-n 5, -n5);
    long: {"all": "a"} long boolean option -> short flag; long_arg: {"lines": "n"} long option taking a value (--lines=5 or --lines 5);
    numeric: if set, -NUM is accepted and stored in values[numeric] (head -5); stop_at_positional: stop parsing at the first non-option.
    Returns None after printing the real error text when something is wrong.
    """
    long, long_arg = long or {}, long_arg or {}
    o = Opts()
    it = iter(range(len(args)))
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            o.rest.extend(args[i + 1:])
            break
        if a.startswith("--") and len(a) > 2:
            name, eq, val = a[2:].partition("=")
            matches = [k for k in list(long) + list(long_arg) if k == name] or [k for k in list(long) + list(long_arg) if k.startswith(name)]
            if len(matches) != 1:
                if not matches:
                    ctx.err(f"{ctx.name}: unrecognized option '--{name}'")
                else:
                    ctx.err(f"{ctx.name}: option '--{name}' is ambiguous")
                ctx.err(f"Try '{ctx.name} --help' for more information.")
                return None
            key = matches[0]
            if key in long_arg:
                if not eq:
                    i += 1
                    if i >= len(args):
                        ctx.err(f"{ctx.name}: option '--{key}' requires an argument")
                        ctx.err(f"Try '{ctx.name} --help' for more information.")
                        return None
                    val = args[i]
                o.values.setdefault(long_arg[key], []).append(val)
                o.flags.add(long_arg[key])
            else:
                o.flags.add(long[key])
                o.flags.add(key)
            i += 1
            continue
        if a.startswith("-") and len(a) > 1 and not (numeric and a[1:].isdigit() and False):
            body = a[1:]
            if numeric and body.isdigit():
                o.values.setdefault(numeric, []).append(body)
                o.flags.add(numeric)
                i += 1
                continue
            j = 0
            while j < len(body):
                c = body[j]
                if c in with_arg:
                    val = body[j + 1:]
                    if not val:
                        i += 1
                        if i >= len(args):
                            ctx.err(f"{ctx.name}: option requires an argument -- '{c}'")
                            ctx.err(f"Try '{ctx.name} --help' for more information.")
                            return None
                        val = args[i]
                    o.values.setdefault(c, []).append(val)
                    o.flags.add(c)
                    break
                if c in short:
                    o.flags.add(c)
                    j += 1
                    continue
                ctx.err(f"{ctx.name}: invalid option -- '{c}'")
                ctx.err(f"Try '{ctx.name} --help' for more information.")
                return None
            i += 1
            continue
        if stop_at_positional:
            o.rest.extend(args[i:])
            break
        o.rest.append(a)
        i += 1
    return o
