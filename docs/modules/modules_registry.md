# modules_registry
[Back to Architecture Overview](../README.md)

## Purpose
Provide a shared registry for detector instances so that heavy models are loaded once and reused across modules.

## Key Classes
None

## Key Functions
- **register_detector(name, obj)** - Store detector instance under ``name``.
- **get_detector(name)** - Retrieve a previously registered detector instance.

## Inputs and Outputs
Refer to function signatures above for usage details.

## Dependencies
None
