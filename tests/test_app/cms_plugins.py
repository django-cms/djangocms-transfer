from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool

from .models import Article, ArticlePluginModel, LayoutPluginModel


class RandomPlugin(CMSPluginBase):
    model = Article
    render_plugin = False


class ArticlePlugin(CMSPluginBase):
    model = ArticlePluginModel
    render_plugin = False


plugin_pool.register_plugin(RandomPlugin)
plugin_pool.register_plugin(ArticlePlugin)


class GridRowPlugin(CMSPluginBase):
    model = LayoutPluginModel
    render_template = "page.html"
    allow_children = True


class GridColumnPlugin(GridRowPlugin):
    pass


plugin_pool.register_plugin(GridRowPlugin)
plugin_pool.register_plugin(GridColumnPlugin)
