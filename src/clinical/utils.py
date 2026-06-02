class MockRequest:
    def __init__(self, user, provider):
        self.user = user
        self.user_roles = ["cdisc"]
        self.provider = provider
        self.META = {}
