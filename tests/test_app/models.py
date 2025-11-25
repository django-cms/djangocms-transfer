from cms.models import CMSPlugin
from django.db import models


class Article(CMSPlugin):
    title = models.CharField(max_length=50)
    section = models.ForeignKey('Section', on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.title} -- {self.section}"


class Section(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class ArticlePluginModel(CMSPlugin):
    title = models.CharField(max_length=50)
    sections = models.ManyToManyField('Section')

    def __str__(self):
        return self.title
