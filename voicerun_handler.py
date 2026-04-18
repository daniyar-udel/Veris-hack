from primfunctions.context import Context
from primfunctions.events import Event, StartEvent, TextToSpeechEvent


async def handler(event: Event, context: Context):
    if isinstance(event, StartEvent):
        script = context.get_data("script", "You have a new urgent InboxROI alert.")
        voice = context.get_data("voice", "nova")
        yield TextToSpeechEvent(text=script, voice=voice)
