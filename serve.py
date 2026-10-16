"""The endpoint: serves harness.solve over the serve protocol on $PORT. harness.py holds the agent."""
import harness
import taskbridge

if __name__ == "__main__":
    taskbridge.run(harness.solve)
