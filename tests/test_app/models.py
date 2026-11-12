from django.db import models

from cms.models import CMSPlugin


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


class LayoutPluginModel(CMSPlugin):
    ui_item = models.CharField(max_length=30)
    tag_type = models.CharField(max_length=30, blank=True)
    config = models.JSONField(default=dict)

    def get_short_description(self):
        return self.config.get("plugin_title", {}).get("title", "") or self.config.get("attributes", {}).get("id", "")
