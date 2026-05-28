class ObservabilityRouter:
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'async_jobs' and model.__name__ == 'Metric':
            return 'observability'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'async_jobs' and model.__name__ == 'Metric':
            return 'observability'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'async_jobs' and model_name == 'metric':
            return db == 'observability'
        if app_label == 'async_jobs' and model_name == 'job':
            return db == 'default'
        return None
