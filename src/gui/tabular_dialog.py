from .tabular_dialog_ui import TabularDialogUi
from .simple_dialogs import save_file_dialog, error_dialog
from .settings_dialog import SettingsDialog, SettingsTab
from .settings import Settings
from .help import show_help
from lib import SParamFile, PlotData, Si, AppPaths, Clipboard, parse_si_range, format_si_range
import dataclasses
import io
import pathlib
import re
import math
import itertools
import enum
import pandas as pd
import numpy as np



class TabularDatasetBase:
    @property
    def name(self) -> str:
        raise NotImplementedError()
    @property
    def display_name(self) -> str:
        raise NotImplementedError()
    @property
    def xcol(self) -> str:
        raise NotImplementedError()
    @property
    def ycols(self) -> list[str]:
        raise NotImplementedError()
    @property
    def xcol_data(self) -> np.ndarray:
        raise NotImplementedError()
    @property
    def ycol_datas(self) -> list[np.ndarray]:
        raise NotImplementedError()
    @property
    def is_spar(self) -> bool:
        raise NotImplementedError()
    


class TabularDataset(TabularDatasetBase):
    def __init__(self, name: str, xcol: str, ycols: list[str], xcol_data: np.ndarray, ycol_datas: list[np.ndarray], is_spar: bool):
        self._name, self._xcol, self._ycols, self._xcol_data, self._ycol_datas, self._is_spar = name, xcol, ycols, xcol_data, ycol_datas, is_spar
    @property
    def name(self) -> str:
        return self._name
    @property
    def display_name(self) -> str:
        return self.name
    @property
    def xcol(self) -> str:
        return self._xcol
    @property
    def ycols(self) -> list[str]:
        return self._ycols
    @property
    def xcol_data(self) -> np.ndarray:
        return self._xcol_data
    @property
    def ycol_datas(self) -> list[np.ndarray]:
        return self._ycol_datas
    @property
    def is_spar(self) -> bool:
        return self._is_spar

    @staticmethod
    def create(dataset: any) -> "TabularDataset":
        if isinstance(dataset, SParamFile):
            return TabularDatasetSFile(dataset)
        elif isinstance(dataset, PlotData):
            return TabularDatasetPlot(dataset)
        else:
            raise ValueError()
    


@dataclasses.dataclass
class TabularDatasetSFile(TabularDataset):
    file: SParamFile
    @property
    def name(self) -> str:
        return self.file.name
    @property
    def display_name(self) -> str:
        return 'S-Param: ' + self.name
    @property
    def xcol(self) -> str:
        return 'Frequency'
    @property
    def ycols(self) -> list[str]:
        cols = []
        for ep in range(self.file.nw.nports):
            for ip in range(self.file.nw.nports):
                if ep>=10 or ip>=10:
                    cols.append(f'S{ep+1},{ip+1}')
                else:
                    cols.append(f'S{ep+1}{ip+1}')
        return cols
    @property
    def xcol_data(self) -> np.ndarray:
        return self.file.nw.f
    @property
    def ycol_datas(self) -> list[np.ndarray]:
        result = []
        for ep in range(self.file.nw.nports):
            for ip in range(self.file.nw.nports):
                result.append(self.file.nw.s[:,ep,ip])
        return result
    @property
    def is_spar(self) -> bool:
        return True
    
@dataclasses.dataclass
class TabularDatasetPlot(TabularDataset):
    plot: PlotData
    @property
    def name(self) -> str:
        return self.plot.name
    @property
    def display_name(self) -> str:
        return 'Plot: ' + self.name
    @property
    def xcol(self) -> str:
        return self.plot.x.name
    @property
    def ycols(self) -> list[str]:
        cols = [self.plot.y.name]
        if (self.plot.z is not None):
            cols.append(self.plot.z.name)
        return cols
    @property
    def xcol_data(self) -> np.ndarray:
        return self.plot.x.values
    @property
    def ycol_datas(self) -> list[np.ndarray]:
        result = [self.plot.y.values]
        if (self.plot.z is not None):
            result.append(self.plot.z.values)
        return result
    @property
    def is_spar(self) -> bool:
        return False
    



class TabularFormat(enum.IntEnum):
    dB = 0
    Lin = 1
    Phase = 2
    dB_Phase = 3
    Lin_Phase = 4
    Real_Imag = 5

TABULAR_FORMAT_NAMES = {
    TabularFormat.dB: 'dB',
    TabularFormat.Lin: 'Linear Magnitude',
    TabularFormat.dB_Phase: 'dB, Phase',
    TabularFormat.Lin_Phase: 'Linear Magnitude, Phase',
    TabularFormat.Phase: 'Phase',
    TabularFormat.Real_Imag: 'Real, Imaginary',
}
    


class TabularDialog(TabularDialogUi):

    
    DISPLAY_PREC = 5
    

    def __init__(self, parent):
        super().__init__(parent)
        self.datasets: list[TabularDataset] = []

        self.ui_set_formats_list(list(TABULAR_FORMAT_NAMES.values()))
        self.ui_set_freq_filters_list([
            format_si_range(any, any, allow_total_wildcard=True),
            format_si_range(0, 100e9),
        ])
        self.ui_set_param_filters_list([
            '*',
            'S21',
            'S11 S21 S22',
            'S11 S21 S12 S22',
            'S11 S22',
        ])
    

    def show_modal_dialog(self, datasets: list[any], initial_selection: int = None):
        assert len(datasets) > 0
        self.datasets = [TabularDataset.create(dataset) for dataset in datasets]
        if initial_selection:
            selected_name = self.datasets[initial_selection].display_name
        else:
            selected_name = None
        self.ui_set_datasets_list([ds.display_name for ds in self.datasets], selection=selected_name)
        Settings.attach(self.on_settings_change)
        super().ui_show_modal()


    @property
    def selected_dataset(self) -> TabularDataset:
        if not self.ui_selected_dataset:
            return None
        datasets = [ds for ds in self.datasets if ds.display_name==self.ui_selected_dataset]
        if len(datasets) < 1:
            return None
        return datasets[0]


    @property
    def selected_format(self) -> TabularFormat:
        for format,name in TABULAR_FORMAT_NAMES.items():
            if self.ui_selected_format == name:
                return format
        return TabularFormat.dB  # fallback
    

    def update_data(self):
        if self.selected_dataset:
            self.populate_table(self.selected_dataset)
        else:
            self.clear_table()
    

    def clear_table(self):
        self.ui_populate_table([], [])

        
    def populate_table(self, dataset: "TabularDataset"):
        ds_fmt = self.format_dataset(self.filter_dataset(dataset))
        headers = [ds_fmt.xcol, *ds_fmt.ycols]
        columns = [
            [str(Si(x,significant_digits=TabularDialog.DISPLAY_PREC)) for x in ds_fmt.xcol_data],
            *[[f'{y:.{TabularDialog.DISPLAY_PREC}g}' for y in col] for col in ds_fmt.ycol_datas]
        ]
        self.ui_populate_table(headers, columns)

        
    def copy_data_csv(self, dataset: "TabularDataset"):
        ds_fmt = self.format_dataset(self.filter_dataset(dataset))
        df = self.get_dataframe(ds_fmt)
        sio = io.StringIO()
        df.to_csv(sio, index=None, sep=Settings.csv_separator)
        Clipboard.copy_string(sio.getvalue())

        
    def copy_data_numpy(self, dataset: "TabularDataset"):
        dataset = self.filter_dataset(dataset)
        def split_words(name: str) -> str:
            return re.split(r'\W|^(?=\d)', name)
        def sanitize_var_name(name: str) -> str:
            return '_'.join([w.lower() for w in split_words(name)])
        def sanitize_class_name(name: str) -> str:
            return ''.join([w.capitalize() for w in split_words(name)])
        def format_value(x) -> str:
            return f'{x:.{TabularDialog.DISPLAY_PREC}g}'
        py = 'import numpy as np\n\n'
        py += f'class {sanitize_class_name(dataset.name)}:  # {dataset.name}\n'
        py += f'\t{sanitize_var_name(dataset.xcol)} = np.array([{", ".join([format_value(x) for x in dataset.xcol_data])}])\n'
        for col_name,col_data in zip(dataset.ycols,dataset.ycol_datas):
            py += f'\t{sanitize_var_name(col_name)} = np.array([{", ".join([format_value(x) for x in col_data])}])\n'
        if len(dataset.ycols) >= 1:
            py += '\n'
            py += 'import plotly.graph_objects as go\n\n'
            py += f'fig = go.Figure()\n'
            for col_name in dataset.ycols:
                y_py = f'{sanitize_class_name(dataset.name)}.{sanitize_var_name(col_name)}'
                if dataset.is_spar:
                    y_py = f'20*np.log10(np.maximum(1e-15,np.abs({y_py})))'
                n_py = col_name.replace("'",'"')
                py += f'fig.add_trace(go.Scatter(x={sanitize_class_name(dataset.name)}.{sanitize_var_name(dataset.xcol)}, y={y_py}, name=\'{n_py}\'))\n'
            x_py = dataset.xcol.replace("'",'"')
            py += f'fig.update_layout(xaxis_title=\'{x_py}\')\n'
            if dataset.is_spar:
                py += 'fig.update_layout(yaxis_title=\'dB\')\n'
            py += f'fig.show()\n'
        Clipboard.copy_string(py)

        
    def copy_data_pandas(self, dataset: "TabularDataset"):
        dataset = self.filter_dataset(dataset)
        def split_words(name: str) -> str:
            return re.split(r'\W|^(?=\d)', name)
        def sanitize_var_name(name: str) -> str:
            return '_'.join([w.lower() for w in split_words(name)])
        def format_value(x) -> str:
            return f'{x:.{TabularDialog.DISPLAY_PREC}g}'
        py = 'import pandas as pd\n\n'
        py += f'df_{sanitize_var_name(dataset.name)} = pd.DataFrame({{\n'
        py += f'\t\'{dataset.xcol}\': [{", ".join([format_value(x) for x in dataset.xcol_data])}],\n'
        for n,d in zip(dataset.ycols,dataset.ycol_datas):
            py += f'\t\'{n}\': [{", ".join([format_value(x) for x in d])}],\n'
        py += f'}})  # {dataset.name}\n\n'
        py += f'display(df_{sanitize_var_name(dataset.name)})\n'
        Clipboard.copy_string(py)
    

    def get_dataframe(self, dataset: "TabularDataset") -> "pd.DataFrame":
        data = { dataset.xcol: dataset.xcol_data }
        for name,arr in zip(dataset.ycols,dataset.ycol_datas):
            data[name] = arr
        return pd.DataFrame(data)


    def save_csv(self, dataset: "TabularDataset", filename: str):
        df = self.get_dataframe(dataset)
        df.to_csv(filename, sep=Settings.csv_separator, index=None)


    def save_spreadsheet(self, dataset: "TabularDataset", filename: str):
        df = self.get_dataframe(dataset)
        df.to_excel(filename, sheet_name=dataset.name, index=None, freeze_panes=[1,0])


    def save_spreadsheets_all(self, filename: str):
        names = [dataset.name for dataset in self.datasets]
        dataframes = [self.get_dataframe(self.filter_dataset(dataset)) for dataset in self.datasets]

        writer = pd.ExcelWriter(filename)
        for name,df in zip(names,dataframes):
            df.to_excel(writer, sheet_name=name, index=None, freeze_panes=[1,0])
        writer.close()
    

    def get_filters(self) -> tuple[tuple[float,float],str]:
        
        def parse_cols(s: str):
            s = s.strip()
            if s=='*':
                return any
            parts = [p for p in re.split(r'\s+', s) if p!='']
            return parts

        filter_x = parse_si_range(self.ui_selected_freq_filter)
        filter_cols = parse_cols(self.ui_selected_param_filter)
        
        self.ui_indicate_freq_filter_error(filter_x==(None,None))

        return filter_x, filter_cols


    def filter_dataset(self, dataset: TabularDataset) -> TabularDataset:
        
        ycols = dataset.ycols
        xcol_data = dataset.xcol_data
        ycol_datas = dataset.ycol_datas

        (filter_x0, filter_x1), filter_cols = self.get_filters()

        if not dataset.is_spar:
            filter_cols = any  # ignore filter
        
        if filter_x0 is None or filter_x1 is None:
            return TabularDataset('', '', [''], np.zeros([0]), [np.zeros([0])], False)
        
        if filter_cols is not any:
            ycols_filtered = []
            ycol_datas_filtered = []
            for col in filter_cols:
                found = False
                for colname,coldata in zip(ycols, ycol_datas):
                    if colname.casefold() == col.casefold():
                        found = True
                        ycols_filtered.append(colname)
                        ycol_datas_filtered.append(coldata)
                        break
                if not found:
                    return TabularDataset('', '', [''], np.zeros([0]), [np.zeros([0])], False)
            ycols, ycol_datas = ycols_filtered, ycol_datas_filtered
        
        mask = (xcol_data >= filter_x0) & (xcol_data <= filter_x1)
        xcol_data = xcol_data[mask]
        for i in range(len(ycol_datas)):
            ycol_datas[i] = ycol_datas[i][mask]
        
        return TabularDataset(dataset.name, dataset.xcol, ycols, xcol_data, ycol_datas, dataset.is_spar)


    def format_dataset(self, dataset: TabularDataset) -> TabularDataset:
        
        def interleave_lists(*lists):
            return list(itertools.chain(*zip(*lists)))
        
        ycols = dataset.ycols
        ycol_datas = dataset.ycol_datas

        if dataset.is_spar:
            selected_format = self.selected_format
            if selected_format == TabularFormat.dB_Phase:
                if Settings.phase_unit == 'rad':
                    ycols = interleave_lists(
                        [f'|{name}| / dB' for name in ycols],
                        [f'∠{name} / rad' for name in ycols])
                    ycol_datas = interleave_lists(
                        [20*np.log10(np.maximum(1e-15,np.abs(col))) for col in ycol_datas],
                        [np.angle(col) for col in ycol_datas])
                else:
                    ycols = interleave_lists(
                        [f'|{name}| / dB' for name in ycols],
                        [f'∠{name} / °' for name in ycols])
                    ycol_datas = interleave_lists(
                        [20*np.log10(np.maximum(1e-15,np.abs(col))) for col in ycol_datas],
                        [np.angle(col)*180/math.pi for col in ycol_datas])
            
            elif selected_format == TabularFormat.Lin_Phase:
                if Settings.phase_unit == 'rad':
                    ycols = interleave_lists(
                        [f'|{name}|' for name in ycols],
                        [f'∠{name} / rad' for name in ycols])
                    ycol_datas = interleave_lists(
                        [np.abs(col) for col in ycol_datas],
                        [np.angle(col) for col in ycol_datas])
                else:
                    ycols = interleave_lists(
                        [f'|{name}|' for name in ycols],
                        [f'∠{name} / °' for name in ycols])
                    ycol_datas = interleave_lists(
                        [np.abs(col) for col in ycol_datas],
                        [np.angle(col)*180/math.pi for col in ycol_datas])

            elif selected_format == TabularFormat.dB:
                ycols = [f'|{name}| / dB' for name in ycols]
                ycol_datas = [20*np.log10(np.maximum(1e-15,np.abs(col))) for col in dataset.ycol_datas]

            elif selected_format == TabularFormat.Lin:
                ycols = [f'|{name}|' for name in ycols]
                ycol_datas = [np.abs(col) for col in dataset.ycol_datas]

            elif selected_format == TabularFormat.Real_Imag:
                ycols = interleave_lists(
                    [f'ℜ𝔢 {name}' for name in ycols],
                    [f'ℑ𝔪 {name}' for name in ycols])
                ycol_datas = interleave_lists(
                    [np.real(col) for col in dataset.ycol_datas],
                    [np.imag(col) for col in dataset.ycol_datas])
            
            elif selected_format == TabularFormat.Phase:
                if Settings.phase_unit == 'rad':
                    ycols = [f'∠{name} / rad' for name in ycols]
                    ycol_datas = [np.angle(col) for col in dataset.ycol_datas]
                else:
                    ycols = [f'∠{name} / °' for name in ycols]
                    ycol_datas = [np.angle(col)*180/math.pi for col in dataset.ycol_datas]
            
            else:
                raise ValueError(f'Invalid combobox selection: {format}')
        else:
            # dataset is not S-params, so formatting of the data is probably not intended
            pass
        
        return TabularDataset( dataset.name, dataset.xcol, ycols, dataset.xcol_data, ycol_datas, dataset.is_spar)
    

    def on_settings_change(self):
        self.update_data()


    def on_change_dataset(self):
        if self.selected_dataset:
            can_change_format = self.selected_dataset.is_spar
            self.ui_enable_format_selection(can_change_format)
        self.update_data()


    def on_change_format(self):
        self.update_data()


    def on_change_freq_filter(self):
        self.update_data()


    def on_change_param_filter(self):
        self.update_data()


    def on_save(self):
        if not self.selected_dataset:
            return
        dataset = self.filter_dataset(self.selected_dataset)

        filename: str = save_file_dialog(
            self,
            title='Save Tabular Data',
            filetypes=(
                ('CSV','.csv'),
                ('Spreadsheet','.xlsx'),
                ('All Files','*'),
            ))
        if not filename:
            return

        ext = pathlib.Path(filename).suffix.lower()
        if ext == '.xlsx':
            self.save_spreadsheet(dataset, filename)
        elif ext == '.csv':
            self.save_csv(dataset, filename)
        else:
            error_dialog('Error', 'Saving failed.', f'Unknown extension: {ext}')


    def on_save_all(self):
        assert len(self.datasets) > 0

        filename: str = save_file_dialog(
            self,
            title='Save All Tabular Data',
            filetypes=(
                ('Spreadsheet','.xlsx'),
                ('All Files','*'),
            ))
        if not filename:
            return

        self.save_spreadsheets_all(filename)


    def on_copy_csv(self):
        if not self.selected_dataset:
            return
        self.copy_data_csv(self.selected_dataset)


    def on_copy_numpy(self):
        if not self.selected_dataset:
            return
        self.copy_data_numpy(self.selected_dataset)


    def on_copy_pandas(self):
        if not self.selected_dataset:
            return
        self.copy_data_pandas(self.selected_dataset)


    def on_settings(self):
       SettingsDialog(self).show_modal_dialog(SettingsTab.Format)


    def on_help(self):
        show_help('tools.md')
