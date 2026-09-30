# Remote policy protocol (`robo-evals/1`)

Use the remote protocol to evaluate a policy that runs in a different process, Python
environment, or machine from the harness. The harness is always the client. Your policy server
answers one request at a time for a given evaluation.

## Encoding

Every message is a JSON object.

- One-dimensional arrays (positions, `state`) travel as JSON lists of numbers.
- Arrays with two or more dimensions (camera images) travel as an object:

  ```json
  {"__ndarray__": "<base64 of the raw C-order bytes>", "dtype": "uint8", "shape": [128, 128, 3]}
  ```

- Strings, such as `instruction`, travel as JSON strings.

The action you return is a list of 4 numbers, `[dx, dy, dz, grip]`. The harness clips each value
to `[-1, 1]` and rejects NaN or infinity.

## HTTP

| Method and path | Request body | Response body |
| --- | --- | --- |
| `GET /info` | none | `{"protocol": "robo-evals/1", "name": "..."}` |
| `POST /reset` | `{"task": str, "seed": int, "instruction": str}` | `{}` (any JSON object) |
| `POST /act` | `{"observation": {...}}` | `{"action": [4 numbers]}` |

The harness calls `/reset` before every episode and `/act` once per control step. Return a non-200
status to signal an error. The harness stops the run and shows the response body.

## WebSocket

Open one connection per evaluation. Send one message and read one reply at a time.

| You receive | You reply |
| --- | --- |
| `{"type": "reset", "task": str, "seed": int, "instruction": str}` | `{"type": "ok"}` |
| `{"type": "act", "observation": {...}}` | `{"type": "action", "action": [4 numbers]}` |
| `{"type": "info"}` | `{"type": "info", "protocol": "robo-evals/1", "name": "..."}` |

On failure, reply `{"type": "error", "message": str}`.

## Serving a model

The fastest path is `robo-evals serve --policy module:attr [--protocol ws]`, which wraps any
Python policy. If your model needs its own environment, copy
[`examples/policy_server.py`](../examples/policy_server.py), which uses only the standard library,
and replace its `act` function with your model's forward pass. A typical adapter for a
vision-language-action model:

1. Decode `observation["image"]` into the tensor layout your model expects.
2. Pass `observation["instruction"]` as the language prompt.
3. Map the model's output into the `[dx, dy, dz, grip]` action space. One unit of `dx` moves the
   end-effector target 3 cm, so scale metric deltas by `1 / 0.03`.

Run with `--image-obs` so observations include the front camera image.
