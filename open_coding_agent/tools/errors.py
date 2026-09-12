class ToolError(Exception):
    """Raised by any tool for a usage error (bad path, refused action, missing
    file, ...). The message is fed back to the model as the tool result so it
    can adapt, instead of crashing the session. Lives in its own module because
    every tool module raises it; none of them owns it."""
