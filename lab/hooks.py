"""Temporary hooks capture each block's residual stream after attention and the MLP."""

from contextlib import contextmanager


def hidden(output):
    return output[0] if isinstance(output, tuple) else output


@contextmanager
def capture(blocks, layers=None):
    states = {}
    handles = []
    try:
        for layer in range(len(blocks)) if layers is None else layers:
            def save(module, inputs, output, index=layer):
                states[index] = hidden(output).detach().clone()
            handles.append(blocks[layer].register_forward_hook(save))
        yield states
    finally:
        for handle in handles:
            handle.remove()


@contextmanager
def patch(block, position, replacement):
    def replace(module, inputs, output):
        state = hidden(output).clone()
        if replacement.shape != state[:, position, :].shape:
            raise ValueError("The patch shape does not match the selected activation.")
        state[:, position, :] = replacement
        return (state,) + output[1:] if isinstance(output, tuple) else state

    handle = block.register_forward_hook(replace)
    try:
        yield
    finally:
        handle.remove()
