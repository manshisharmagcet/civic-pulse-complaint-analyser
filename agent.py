"""CivicPulse - hosted uAgent that analyzes citizen civic complaints."""

from uagents import Agent, Context

from protocols import protocol

agent = Agent()


@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info("CivicPulse is live and ready to analyze civic complaints.")


agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
