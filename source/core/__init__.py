"""AI Core — the balanced center of the geometric nesting.

Everything in here is shared by the client and by every ring service:
the wire contract (TOOL: tokens for the model surface, JSON actions on
the sockets), the socket caller, and the response constructors.

The geometry may be rearranged; this contract may not. See
docs/GEOMETRIC_NESTING.md.
"""
