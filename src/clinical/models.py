from django.db import models


class ClinicalEntity(models.Model):
    external_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# Level 1
class Study(ClinicalEntity):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Site(ClinicalEntity):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="sites")
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


# Level 2
class Subject(ClinicalEntity):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="subjects")
    name = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name or self.external_id


class Form(ClinicalEntity):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="forms")
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Interval(ClinicalEntity):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="intervals")
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


# Level 3
class Variable(ClinicalEntity):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="variables")
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Visit(ClinicalEntity):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="visits")
    interval = models.ForeignKey(Interval, on_delete=models.CASCADE, related_name="visits")

    def __str__(self):
        return f"{self.subject} - {self.interval}"


# Level 4
class Record(ClinicalEntity):
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="records")
    variable = models.ForeignKey(Variable, on_delete=models.CASCADE, related_name="records")
    value = models.TextField(blank=True)


class Coding(ClinicalEntity):
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="codings")
    code = models.CharField(max_length=255)


class Query(ClinicalEntity):
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="queries")
    text = models.TextField()


class Revision(ClinicalEntity):
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="revisions")
    value = models.TextField()
