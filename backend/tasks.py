from celery_app import celery

@celery.task
def hello():

    print("Hello from Celery")

    return "Done"