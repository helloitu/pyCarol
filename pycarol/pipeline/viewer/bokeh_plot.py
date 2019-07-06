import bokeh
assert bokeh.__version__ == '1.2.0'
from bokeh.models import (
    ColumnDataSource,
    BooleanFilter,
    HoverTool,
)

from bokeh.events import ButtonClick
from bokeh.models import Button
from bokeh.layouts import widgetbox
from bokeh.models.widgets import PreText

from bokeh.layouts import column, row, layout
from bokeh.plotting import figure
from bokeh.transform import transform
from bokeh.palettes import Category10
from bokeh.models.mappers import CategoricalColorMapper

# Annotation imports
from typing import Type, List
from pycarol.pipeline import Pipe, Task


def _make_colormapper(data_source: dict, col_name: str):
    import numpy as np
    factors = list(set(data_source[col_name]))
    nb_factors = np.clip(len(factors), 3, 10)
    return CategoricalColorMapper(factors=factors,
                                  palette=Category10[nb_factors])



def _make_pipeline_plot(
        nodes_data_source: Type[ColumnDataSource],
        edges_data_source: Type[ColumnDataSource],
):
    def _update_incomplete(nodes_data_source,incomplete_nodes_data_source):
        nodes_dict = nodes_data_source.data
        incomplete_mask = [(not c) for c in nodes_dict['complete']]
        incomplete_dict = {
            'x': [x for i,x in enumerate(nodes_dict['x']) if incomplete_mask[i]],
            'y': [x for i,x in enumerate(nodes_dict['y']) if incomplete_mask[i]]
            }
        incomplete_nodes_data_source.data = incomplete_dict

    incomplete_nodes_data_source = ColumnDataSource()
    _update_incomplete(nodes_data_source,incomplete_nodes_data_source)
    nodes_data_source.on_change(
        'data',
        lambda attr,old,new: _update_incomplete(nodes_data_source,incomplete_nodes_data_source)
        )

    family_color = _make_colormapper(nodes_data_source.data,'task_family')
    #TODO(renan): remove grid. set light  gray background color
    #TODO(renan): add more info to tooltips
    pipeline_plot = figure(
        title="Pipeline Debugger",
        x_range=(-1, max(nodes_data_source.data['x']) + 1),
        y_range=(-1, max(nodes_data_source.data['y']) + 1),
        tools=[
            HoverTool(names=['alltasks']),
            'wheel_zoom',
            'pan',
            'tap',
            'box_select',
            'reset'
        ],
        toolbar_location='right',
        tooltips=[
            ('index', "$index"),
            ('task_id', '@task_id'),
        ],
        plot_width=900,
        plot_height=500,
    )

    edges_glyph = pipeline_plot.segment(
        'x0',
        'y0',
        'x1',
        'y1',
        source=edges_data_source,
        color='gray',
        line_alpha=0.3,
    )
    #TODO(renan): check/show hash version is equal
    pipeline_plot.circle(
        'x',
        'y',
        source=nodes_data_source,
        size=20,
        name='alltasks',
        color=transform('task_family', family_color),
        legend='task_family',
    )

    pipeline_plot.circle(
        'x',
        'y',
        source=incomplete_nodes_data_source,
        size=10,
        color='white',
    )
    
    pipeline_plot.text(
        x='x',
        y='y',
        text='task_name',
        source=nodes_data_source,
        text_font_size='8pt',
    )

    edges_glyph.nonselection_glyph = None
    return pipeline_plot

#TODO: make plotsdynamics abstract class with button decorator and so on
class PlotDynamics():
    def __init__(
            self,
            nodes_data_source: Type[ColumnDataSource],
            edges_data_source: Type[ColumnDataSource],
            pipe: Type[Pipe],
    ):
        nodes_data_source.selected.on_change(
            'indices', self.select_callback
        )

        self.remove_button = Button(label='Remove Selected')
        self.removeupstream_button = Button(label='Remove Upstream')
        self.update_button = Button(label='Update')
        self.run_button = Button(label='Run')
        self.close_button = Button(label='Close')

        self.remove_button.on_event(
            ButtonClick,
            self.remove_callback,
        )
        self.removeupstream_button.on_event(
            ButtonClick,
            self.removeupstream_callback,
        )
        self.update_button.on_event(
            ButtonClick,
            self.update_callback,
        )
        self.run_button.on_event(
            ButtonClick,
            self.run_callback,
        )
        self.close_button.on_event(ButtonClick,self.close_callback)


        self.nodes_data_source = nodes_data_source
        self.edges_data_source = edges_data_source
        self.selected_nodes = []
        assert isinstance(pipe, Pipe)
        self.pipe = pipe

    def get_selected_tasks(self) -> List[Type[Task]]:
        task_id_column = self.nodes_data_source.data['task_id']
        task_ids = [task_id_column[i] for i in self.selected_nodes]
        selected_tasks = [self.pipe.get_task_by_id(id) for id in task_ids]
        return selected_tasks

    def select_callback(self,attr, old, new):
        self.selected_nodes = new
        # pre.text = self.tasklog[new[0]]
        print("selected {}".format(new))


    def run_callback(self,event):
        print("entered run callback")
        for t in self.get_selected_tasks():
            print(f"Running {t}")
            t.run()

    def remove_callback(self,event):
        for t in self.get_selected_tasks():
            print(f"Removing {t}")
            t.remove()

    def close_callback(self,event):
        from tornado.ioloop import IOLoop
        ioloop = IOLoop.current()
        ioloop.stop()

    def removeupstream_callback(self,event):
        for t in self.get_selected_tasks():
            assert isinstance(t,Task), f"{t} should be instance of {Task}"
            print(f"Removing upstream {t}")
            self.pipe.remove_upstream([t])
        return

    def update_callback(self,event):
        task_id_column = self.nodes_data_source.data['task_id']
        old_complete_column = self.nodes_data_source.data['complete']
        new_complete = [self.pipe.get_task_by_id(id).complete() for id in task_id_column]
        if old_complete_column == new_complete:
            print("No changes detected in complete column.")
        else:
            self.nodes_data_source.data['complete'] = new_complete
        
    #TODO: make buttons decorator
    def buttons(self):
        # TODO: return buttons array if too many buttons
        return row([
            self.remove_button,
            self.update_button,
            self.removeupstream_button,
            self.run_button,
            self.close_button,
        ])

def plot_pipeline(
    nodes_data:dict,
    edges_data:dict,
    pipe: Type[Pipe],
    ):
    """
    Receives data sources in dict format and returns dynamic plot
    Args:
        nodes_data:
        edges_data:

    Returns:
        final_layout:

    """
    #TODO: get nodes_data and edges_data from pipe
    nodes_data_source = ColumnDataSource(data=nodes_data)
    edges_data_source = ColumnDataSource(data=edges_data)


    pipeline_plot = _make_pipeline_plot(nodes_data_source, edges_data_source)

    dynamics = PlotDynamics(nodes_data_source,edges_data_source,pipe)

    ### Layout
    final_layout = layout(
        column(
            [
                pipeline_plot,
                row(dynamics.buttons()),
            ],
            sizing_mode='scale_width'
        ),
    )
    return final_layout


def get_plot_from_pipeline(pipe: Type[Pipe]):
    """
    Main module method. From a luigi task with defined parameters, generates a
    bokeh plot of the
    pipeline. It does not render the plot.
    Args:
        pipe: list of luigi task initialised with proper parameters

    Returns:
        bokeh_layout:

    """

    from .viewer import (nodes_layout, edges_layout,
                         make_nodes_data_source, make_edges_data_source,
                         )

    dag = pipe.get_dag()

    nodes_layout = nodes_layout(dag)
    edges_layout = edges_layout(dag, nodes_layout)

    nodes_data_source = make_nodes_data_source(nodes_layout)
    edges_data_source = make_edges_data_source(edges_layout)

    bokeh_layout = plot_pipeline(nodes_data_source, edges_data_source, pipe)

    return bokeh_layout

#TODO: implement python bokeh server to make dev and tests easier: tried with tornado ioloop, but degbugger does not get into async process

