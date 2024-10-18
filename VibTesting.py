 # SYSTEM
import sys
# DCOM
from win32com.client import Dispatch
import pythoncom
# CALCULATIONS
import numpy as np
import math
# UI
from tqdm.notebook import tqdm
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from IPython.display import display, clear_output
from ipywidgets import widgets, Output,  Layout, GridspecLayout
# DATA MANAGEMENT
import json
# OTHER
import time
import winsound



class VibTesting:
    def __init__(self, acquisition_class_instance, imp_force_lim=0.015, double_imp_force_lim=1):
        
        """
        A class allowing for interaction with the acquisition system (either NI or Dewesoft) for purpose of performing impact testing or operational measurements.
        
        PARAMETERS:
        :param acquisition_class_instance: Instance of the acquisition class (NISetup or DSSetup)
        :param imp_force_lim: Force limit for detecting the beginning and end of the impact
        :param double_imp_force_lim: Force limit for detecting double impact

        TODO: Preglej!
        Attributes:
            dw (Dispatch): Dewesoft application instance
            responses (list): List of used responses in the measurement
            chn_dict (dict): Dictionary mapping channel indices to channel names
            acq.sensor_dict (dict): Dictionary containing sensor details for each channel
            response_names (list): List of channel names to be used in the measurement
            impact_names (list): List of impact names
            acq.sampling_rate (float): acq.Sampling rate of the acquisition system
            samples_per_channel (int): Number of samples per channel
            acq.acquisition_time (float): Total acquisition time
            imp_force_lim (float): Force limit for detecting the beginning and end of the impact
            double_imp_force_lim (float): Force limit for detecting double impact
            no_impacts (int): Number of impacts in the measurement series
            meas_file (str): Path to the measurement file
            points_to_measure (list): List of points to measure
            point_ind (int): Current point index in the measurement series
            points_measured (list): List of measured points
            saved (bool): Flag indicating if the measurement data is saved
            admittance (bool): Flag indicating if admittance measurement is enabled
            Y (any): Admittance measurement data
            dof_data (any): Degree of freedom data
            Y_done (any): Flag indicating if admittance measurement is done
            response_names (any): Admittance responses
            impact_names (any): Admittance impacts
            resp_factors (any): Channel factors
            imp_factors (any): Impact factors
        :param acquisition_class_instance: instance of the acquisition class (NISetup or DSSetup)
        

        # MEASUREMENT SETUP PARAMS
        :param response_names: list of channel names to be used in the measurement
        :param impact_names: list of impact names

        # IMPACT TEST PARAMS
        :param imp_force_lim: force limit for detecting beginning and end of the impact
        :param double_imp_force_lim: force limit for detecting double impact
        """
        # ACQUISITION SYSTEM
        self.acq = acquisition_class_instance

        # DOUBLE IMPACT CONTROL
        self.imp_force_lim = imp_force_lim
        self.double_imp_force_lim = double_imp_force_lim

        # MEASUREMENT SERIES VARIABLES
        self.no_impacts = None
        self.meas_file = ''
        self.points_to_measure = []
        self.point_ind = 0
        self.points_measured = []
        self.saved = False
        self.response_names = None
        self.impact_names = None
        

        # ADMITTANCE MEASUREMENT VARIABLES
        self.admittance = False
        self.Y = None
        self.dof_data = None
        self.Y_done = None
        self.Y_done_diff = None
        self.response_names = None
        self.impact_names = None
        self.resp_factors = None
        self.imp_factors = None
        self.no_response_groups = 1
        self.no_unique_impacts = None

    

    def collect_meas_info(self):
        return {'Acquisition system': self.acq.acq_name,
                'Response names': self.response_names,
                'Impact names': self.impact_names,
                'acq.Sampling rate': self.acq.acq.sampling_rate,
                'Acquisiton time': self.acq.acq.acquisition_time,
                'Samples per channel': self.acq.samples_per_channel,
                'Sensor data': self.acq.sensor_dict}

    def reset_series_params(self):
        self.point_ind = 0
        self.points_measured = []
        self.saved = False

    # Impact measurement methods
    def start_impact_test(self, no_impacts, save_to=None, series=False):
        """
        :param no_impacts:
        :param save_to: name of the file in which self.measurements_temp are to be saved.
        :param series: 
        """
        self.no_impacts = no_impacts

        # tqdm
        pbar = tqdm(total=self.no_impacts)
        imp = 0

        while imp < self.no_impacts:
            # Beep denoting start of the measurement
            winsound.Beep(410, 180)
            # Signal acquisition
            imp_data = self.acq.get_impact(imp)
            if imp == 0:
                self.measurement_array = np.zeros((self.no_impacts, imp_data.shape[0], imp_data.shape[1]), dtype=np.float64)
            self.measurement_array[imp, :, :] = imp_data
            # Check for chn overload
            no_overload = self.check_chn_overload(imp)
            # Check for force overload
            no_imp_overload = self.check_imp_overload(imp)
            # check for double imp
            imp_start, imp_end = self.get_imp_start_end(imp)
            double_ind, no_double = self.check_double_impact(imp, imp_end)
            # Check for channel overloads, double impacts
            msg = None
            if (not no_overload) and (not no_double) and (not no_imp_overload):
                msg = 'Double impact and chn #cifra# overload and force overload'
                winsound.PlaySound('SystemHand', winsound.SND_ALIAS)
            elif (not no_overload) and (not no_double):
                msg = 'Chn #cifra# overload and double impact!'
                winsound.PlaySound('SystemHand', winsound.SND_ALIAS)
            elif (not no_double) and (not no_imp_overload):
                msg = 'Double impact and force overload!'
                winsound.PlaySound('SystemHand', winsound.SND_ALIAS)
            elif (not no_overload) and (not no_imp_overload):
                msg = 'Chn #cifra# overload and force overload!'
                winsound.PlaySound('SystemHand', winsound.SND_ALIAS)
            elif not no_overload:
                msg = 'Chn #cifra# overload!'
                winsound.PlaySound('SystemHand', winsound.SND_ALIAS)
            elif not no_double:
                msg = 'Double impact.'
                winsound.PlaySound('SystemHand', winsound.SND_ALIAS)
            elif not no_imp_overload:
                msg = 'Force overload.'
                winsound.PlaySound('SystemHand', winsound.SND_ALIAS)
            else:
                winsound.Beep(300, 70)
            # Plotting acquired signals
            self.plot_imp_meas(imp, msg=msg, imp_start=imp_start, imp_end=imp_end, double_ind=double_ind)
            if msg is None:
                imp += 1
                pbar.update(1)
        winsound.PlaySound("SystemExit", winsound.SND_ALIAS)
        pbar.container.children[-2].style.bar_color = 'green'
        self.save_imp_test_results(save_to, pbar, series=series)

    def start_admittance_measurement(self, responses, impacts, 
                                     resp_factors, imp_factors, no_impacts,
                                     no_response_groups=1,
                                     save_to=None, existing_Y=None, existing_json=None):
        """
        Channel names must be of the same length, impact names must be of the same length.

        :param responses: list of channel names
        :param impacts: list of impact names

        :param resp_factors: list of factors with which the channel data is to be multiplied
        :param imp_factors: list of factors with which the impact data is to be multiplied

        :param no_impacts: number of impacts to be measured

        :param save_to: path to the folder where the measurements are to be saved

        In case of interrupted measurement, measurements can be continued by providing existing_Y and existing_json.
        :param existing_Y: path to the existing Y matrix
        :param existing_json: path to the existing json file with saved measurement progress
        """
        self.admittance = True
        self.response_names, self.impact_names = responses, impacts
        self.no_unique_impacts = len(self.impact_names)
        self.no_responses_in_group = len(self.response_names)
        self.resp_factors, self.imp_factors = resp_factors, imp_factors
        self.no_response_groups = no_response_groups
        self.Y = None

        if self.no_response_groups > 1:
            self.impact_names = [f'{imp_}_gr{gr_+1}' for gr_ in range(self.no_response_groups) for imp_ in self.impact_names]

        self.no_impacts = no_impacts

        if (existing_Y is not None) or (existing_json is not None):  
            if (existing_Y is None) or (existing_json is None):
                raise ValueError('Both existing_Y and existing_json must be provided.')
            else:
                # load existing data
                self.Y = np.load(existing_Y)
                self.dof_data = self.load_from_json(existing_json)
        else:
            # create new data
            self.dof_data = self.get_dof_dict()
            self.Y_done = self.get_done_matrix()
        
        to_do = [_ for _ in self.dof_data['progress'] if self.dof_data['progress'][_] == 0]
        self.save_to_json(save_to + r'\dof_data.json')

        chn_name_length = len(self.response_names[0])
        impacts_to_do = list(set(['F' + _.split('_F')[1] for _ in to_do])) # TODO: 2 zamenjaj za dolžino oznake kanala!
        imp_to_do = [_ for _ in self.impact_names if _ in impacts_to_do] # to ensure correct order of impacts
        self.start_imp_test_series(list_of_points=imp_to_do, no_impacts=self.no_impacts, measurement_file=save_to)

    def start_imp_test_series(self, list_of_points, no_impacts, measurement_file):
        """
        Function allows for impact test series in multiple excitation points.
        
        :param list_of_points: list of points to be measured
        :param measurement_file: path to the folder where the measurements are to be saved
        """
        self.no_impacts = no_impacts
        self.reset_series_params()
        self.points_to_measure = list_of_points
        self.meas_file = measurement_file
        if self.no_response_groups == 1:
            print(f'Measurement point {self.points_to_measure[self.point_ind]}')
        else:
            imp_, gr_ = self.points_to_measure[self.point_ind].split('_')
            gr_ = gr_.replace('gr', '')
            print(f'Measurement group {gr_}, point {imp_}')
        self.start_impact_test(save_to=self.meas_file + fr'\{self.points_to_measure[self.point_ind]}', series=True, no_impacts=self.no_impacts)

    def check_chn_overload(self, imp):
        """
        Function checks if the response signal exceeds 95% of the channel range.
        """
        for i in np.arange(1, self.measurement_array.shape[1]):
            # če vrednost preseže 95% do meje
            chn_min, chn_max = self.acq.sensor_dict[i]['RangeMinValue']*0.95, self.acq.sensor_dict[i]['RangeMaxValue']*0.95
            sig_min, sig_max = min(self.measurement_array[imp, i, :]), max(self.measurement_array[imp, i, :])
            if (sig_min > chn_min) and (sig_max < chn_max):
                return True
            else:
                print(np.where((sig_min < chn_min) or (sig_max > chn_max)))
                return False

    def check_imp_overload(self, imp):
        """
        Function checks if the impact force exceeds 95% of the force channel range.
        """
        imp_ampl = np.max(self.measurement_array[imp, 0, :])
        imp_max = self.acq.sensor_dict[0]['RangeMaxValue']*0.95
        if imp_ampl < imp_max:
            return True
        else:
            return False

    def check_double_impact(self, imp, imp_end):
        ind_ = np.where(self.measurement_array[imp, 0, imp_end:] > self.double_imp_force_lim)[0]
        if len(ind_) > 0:
            return ind_+imp_end, False
        else:
            return None, True

    def get_imp_start_end(self, imp):
        force = self.measurement_array[imp, 0]
        max_force_ind = np.argmax(force)
        start_ = max_force_ind
        while force[start_] > self.imp_force_lim:
            if start_ > (len(force)-1)*-1:
                start_ -= 1
            else: break
        end_ = max_force_ind
        while force[end_] > self.imp_force_lim:
            if end_ < (len(force)-1):
                end_ += 1
            else:
                break
            
        return start_, end_

    # Saving and displaying results
    def save_imp_test_results(self, save_to, pbar, series=False):
        options = [f'Measurement {i+1}' for i in range(self.no_impacts)]
        out = Output()

        # Select self.measurements_temp
        selection = widgets.SelectMultiple(options=options, value=tuple(options), rows=len(options))
        selection.layout = Layout(width='200px')
        # Save measurement info
        save_meas_info_choice = widgets.ToggleButtons(
            options=['No', 'Yes'],
            description='Save measurement info: \n',
            disabled=False,
            button_style='',  # 'success', 'info', 'warning', 'danger' or ''
            style={'description_width': 'initial'}
        )
        # Save self.measurements_temp
        button = widgets.Button(description='Save')

       

        # Buttons for measurement series
        if series:
            saved=False
            repeat_button = widgets.Button(style={'description_width': 'initial'},
                                           description=f'Repeat (point {self.points_to_measure[self.point_ind]})')
            try:
                if self.no_response_groups == 1:
                    next_button_text = f'Next (point {self.points_to_measure[self.point_ind + 1]})'
                else:
                    imp_, gr_ = self.points_to_measure[self.point_ind + 1].split('_')

                    next_button_text = f'Next (Gr.: {gr_[2:]}, point {imp_})'
            except IndexError:
                next_button_text = ''

            next_button = widgets.Button(description=next_button_text, button_style='danger', style={'width':'auto'})
                            
            # admittance plot
            if self.admittance:
                imp_name_ = self.points_to_measure[self.point_ind]
                # set current impact group status to 0.5
                for chn_ in self.response_names:
                    dof_name_str_ = f'{chn_}_{imp_name_}'
                    self.dof_data['progress'][dof_name_str_] = .5
                # update Y_done
                self.get_done_matrix()
                # set current impact group status back to 0
                for chn_ in self.response_names:
                    dof_name_str_ = f'{chn_}_{imp_name_}'
                    self.dof_data['progress'][dof_name_str_] = 0

                adm_checkbox = widgets.Checkbox(value=False, description='Check me', disabled=False)
                adm_checkbox.layout.display = 'none'
                adm_imshow = widgets.interactive(self.plot_Y_done, saved=adm_checkbox)
        else:
            repeat_button, next_button = None, None

        if save_to is None:
            file_name = widgets.Text(description='Save to: ',
                                     placeholder='Filename',
                                     value='')
            widgets_ = [selection, save_meas_info_choice, file_name, button]
        else:
            if not series and not self.admittance:
                widgets_ = [selection, save_meas_info_choice, button]
            elif not self.admittance:
                widgets_ = [selection, save_meas_info_choice, button, repeat_button, next_button]
            else:
                widgets_ = [selection, save_meas_info_choice, button, repeat_button, next_button, adm_imshow]
        display(self.widget_layout(widgets_, save_to, series))

        

        def save_btn_clicked(B, save_to_=save_to):
           
            # update next_button
            next_button.button_style = 'success'
            # save data
            chosen_meas = [int(_[-1])-1 for _ in list(selection.value)]
            if self.admittance:
                # get FRF
                chn_mask = np.array([_ for _ in range(self.measurement_array.shape[1]) if _ != 0])
                imp_name_ = self.points_to_measure[self.point_ind]
                if self.no_response_groups>1:
                    current_group = int(imp_name_.split('_')[-1].replace('gr', ''))
                else:
                    current_group = 1
                imp_ind_ = self.impact_names.index(imp_name_)%self.no_unique_impacts
                impact_ = self.measurement_array[chosen_meas, :][:, 0]*self.imp_factors[imp_ind_]
                channels_ = self.measurement_array[chosen_meas, :][:, chn_mask]*np.array(self.resp_factors)[None, :, None]
                imp_fft_ = np.fft.rfft(impact_).T
                chn_fft_ = np.fft.rfft(channels_).T
                if self.Y is None:
                    self.Y = np.zeros((imp_fft_.shape[0], len(self.response_names)*self.no_response_groups, self.no_unique_impacts), dtype=np.complex128)
                    print(self.Y.shape)
                for chn_ in self.response_names:
                    chn_ind_ = int(self.impact_names.index(imp_name_)//self.no_unique_impacts)*self.no_responses_in_group + self.response_names.index(chn_)
                    self.Y[:, chn_ind_, imp_ind_] = self.get_FRF(chn_fft_[:,chn_ind_%self.no_responses_in_group], imp_fft_)
                    # update dof_data
                    dof_name_str_ = f'{chn_}_{imp_name_}'
                    self.dof_data['progress'][dof_name_str_] = 1
                
                # Plot Y_done in admittance measurement
                self.get_done_matrix()
                adm_checkbox.value = True

                np.save(self.meas_file + r'\Y.npy', self.Y)
            
            self.save_to_json(self.meas_file + r'\dof_data.json')
            if save_to_ is None:
                save_to_ = str(file_name.value)
                if len(save_to_) == 0:
                    message = 'Enter file name!'
                else:
                    message = f'Measurements {chosen_meas} saved to \"{save_to_}.npy\"'
                    np.save(f'{save_to_}.npy', self.measurement_array[chosen_meas, :, :])
                    if save_meas_info_choice.value == 'Yes':
                        message += f'\nMeasurement info saved to \"{save_to_}.json\"'
                        json_obj = json.dumps(self.collect_meas_info(), indent=4)
                        with open(f'{save_to_}.json', 'w') as meas_data_file:
                            meas_data_file.write(json_obj)
                    pbar.container.children[-2].style.bar_color = 'black'
            else:
                np.save(f'{save_to_}.npy', self.measurement_array[chosen_meas, :, :])
                message = f'Measurements {chosen_meas} saved to \"{save_to_}.npy\"'
                if save_meas_info_choice.value == 'Yes':
                    message += f'\nMeasurement info saved to \"{save_to_}.json\"'
                    json_obj = json.dumps(self.collect_meas_info(), indent=4)
                    with open(f'{save_to_}.json', 'w') as meas_data_file:
                        meas_data_file.write(json_obj)
                pbar.container.children[-2].style.bar_color = 'black'
            with out:
                clear_output()
                print(message)
            display(out)

        def repeat_button_clicked(B):
            saved=False
            clear_output(wait=True)
            print(f'Measurement point {self.points_to_measure[self.point_ind]}')
            self.start_impact_test(save_to=self.meas_file + fr'\{self.points_to_measure[self.point_ind]}', no_impacts=self.no_impacts, series=True)

        def next_button_clicked(B):
            saved=False
            try:
                next_point = self.points_to_measure[self.point_ind+1]
                self.points_measured.append(self.points_to_measure[self.point_ind])
                clear_output(wait=False)
                self.point_ind += 1
                print(f'Measurement point {self.points_to_measure[self.point_ind]}')
                self.start_impact_test(no_impacts=self.no_impacts, save_to=self.meas_file + fr'\{next_point}', series=True)
            except IndexError:
                print('All points measured!')
        button.on_click(save_btn_clicked)
        if series:
            repeat_button.on_click(repeat_button_clicked)
            next_button.on_click(next_button_clicked)

    def widget_layout(self, widgets_list, save_to, series):
        grid = GridspecLayout(2+series, 3+series+self.admittance)
        grid[:, 0] = widgets_list[0]
        grid[0, 1:3] = widgets_list[1]
        if save_to is None:
            grid[1, 1] = widgets_list[2]
            grid[1, 2] = widgets_list[3]
        else:
            grid[1, 1:3] = widgets_list[2]
        if series:
            grid[2, 1] = widgets_list[3]
            grid[2, 2] = widgets_list[4]
        if self.admittance:
            grid[:,3] = widgets_list[5]
        return grid

    def close_task(self):
        self.task.close()

    def plot_imp_meas(self, meas_ind, msg, imp_start, imp_end, double_ind=None):
        """
        Plots individual measurement
        :param meas_ind:
        :param msg:
        :param imp_start: index of impact starting point
        :param imp_end: index of impact ending point
        :param double_ind: index of double impact location
        :return:
        """
        plot_min, plot_max = imp_start-15, imp_end+30
        if plot_min < 0:
            plot_min = 0
        if imp_start < 0:
            imp_start = 0
        # print(imp_start, imp_end)
        fig, ax = plt.subplots(1, 4, figsize=(15, 2.5), tight_layout=True)
        mask = np.ones(self.measurement_array.shape[1], dtype=bool)
        mask[0] = 0
        force_ = self.measurement_array[meas_ind, 0, plot_min:plot_max].T
        times = np.arange(self.acq.sampling_rate * self.acq.acquisition_time) / self.acq.sampling_rate
        ax[0].plot(times[plot_min:plot_max], force_)
        try:
            ax[0].vlines(imp_start / self.acq.sampling_rate, min(force_) - 1, max(force_) + 1, color='green',
                         ls='--')
            ax[0].vlines(imp_end/self.acq.sampling_rate, min(force_) - 1, max(force_) + 1, color='red', ls='--')
            ax[0].set_ylim(min(force_) - 1, max(force_) + 1)
        except ValueError:
            print(imp_start, imp_end, plot_min, plot_max)
            pass
        ax[0].set_xticks([imp_start/self.acq.sampling_rate, imp_end/self.acq.sampling_rate])
        ax[0].set_xticklabels([f'{_:.5f}' for _ in [imp_start / self.acq.sampling_rate, imp_end / self.acq.sampling_rate]])
        ax[0].set_title(f'Impact duration: {(imp_end-imp_start)/self.acq.sampling_rate*1000:.3f} ms')
        ax[1].plot(times, self.measurement_array[meas_ind, 0, :].T)
        ax[1].set_title(f'Impact amplitude: {max(force_):.3f} N')
        ax[2].plot(times, self.measurement_array[meas_ind, mask, :].T, lw=.5)
        # TODO: dodaj enoto!
        ax[2].set_title(f'Max. response: {np.max(self.measurement_array[meas_ind, mask, :]):.3f}')
        ax[3].semilogy(abs(np.fft.rfft(self.measurement_array[meas_ind, mask, :])).T, lw=.5)
        if msg is None:
            fig.suptitle(f'Impact {meas_ind + 1}/{self.no_impacts}', fontsize=15)
            fig.patch.set_facecolor('#cafac5')
        else:
            if double_ind[0] < plot_max:
                ax[0].vlines(double_ind[0]-plot_min, min(force_)-1, max(force_)+1, color='k', ls='--')
            ax[1].vlines((double_ind[0])/self.acq.sampling_rate, min(force_) - 1, max(force_) + 1, color='k', ls='--')
            fig.suptitle(f'Impact {meas_ind + 1}/{self.no_impacts} ({msg})', fontsize=12)
            fig.patch.set_facecolor('#faa7a7')

        plt.show()

    

    # Admittance measurement methods
    def get_dof_dict(self):
        rows_, columns_ = np.meshgrid(self.response_names, self.impact_names)
        rows_, columns_ = rows_.flatten(), columns_.flatten()
        dof_dict = {}
        dof_dict['responses'], dof_dict['impacts'] = list(self.response_names), list(self.impact_names)
        dof_dict['resp_factors'], dof_dict['imp_factors'] = list(self.resp_factors), list(self.imp_factors)
        dof_dict['progress'] = {}
        for r_, c_ in zip(rows_, columns_):
            dof_dict['progress'][f'{r_}_{c_}'] = 0
        return dof_dict

    def get_done_matrix(self):
        self.Y_done = np.zeros((len(self.dof_data['responses'])*self.no_response_groups, self.no_unique_impacts))
        rows_, columns_ = np.meshgrid(self.dof_data['responses'], self.dof_data['impacts'])
        rows_, columns_ = rows_.flatten(), columns_.flatten()
        Y_done_old = self.Y_done
        for r_, c_ in zip(rows_, columns_):
                resp_ind_, imp_ind_ = self.dof_data['responses'].index(r_), self.dof_data['impacts'].index(c_)
                self.Y_done[resp_ind_+int(imp_ind_//self.no_unique_impacts)*len(self.dof_data['responses']), int(imp_ind_%self.no_unique_impacts)] = self.dof_data['progress'][f'{r_}_{c_}']
        self.Y_done_diff = np.where(self.Y_done != Y_done_old)
        


    def plot_Y_done(self, saved=False):
        imp_name_len = len(self.impact_names[0])
        if imp_name_len >2:
            rotation=90
        else:
            rotation=0
        plt.figure(figsize=(0.5*len(self.impact_names)//self.no_response_groups, 0.2*len(self.response_names)*self.no_response_groups))
        plt.imshow(self.Y_done, cmap='RdYlGn', vmin=0, vmax=1)
        plt.xlabel('Impacts')
        plt.ylabel('Responses')
        if self.no_response_groups == 1:
            plt.xticks(np.arange(len(self.impact_names)), self.impact_names, rotation=rotation)
            plt.yticks(np.arange(len(self.response_names)), self.response_names)
        else:
            plt.xticks(np.arange(self.no_unique_impacts),
                        [_.split('_')[0] for _ in self.impact_names[:self.no_unique_impacts]], rotation=rotation)
            plt.yticks(np.arange(len(self.response_names)*self.no_unique_impacts), [f'{resp_}_gr{gr_+1}' for gr_ in range(self.no_response_groups) for resp_ in self.response_names])
        ax = plt.gca()
        ax.xaxis.set_minor_locator(MultipleLocator(.5))
        ax.yaxis.set_minor_locator(MultipleLocator(.5))
        ax.grid(which='minor', linewidth=.5)
        plt.show()

    
    @staticmethod
    def get_FRF(X, F, filter_list=None, estimator='H1', kind='admittance'):
        """
        Function calculates frequency response functions (FRF) from measurement data.
        :param X: np.array of accelerations (frequencies, repeated self.measurements_temp)
        :param F: np.array of accelerations (frequencies, repeated self.measurements_temp)
        :param filter_list: list of indices of self.measurements_temp to be excluded from the FRF calculation
        :param estimator: FRF estimator (H1, H2)
        :param kind: FRF type (admittance/impedance)
        :return: averaged FRF
        """
        N = X.shape[1]
        # Izračun cenilk prenosne funkcije
        if estimator == 'H1':
            S_fx_avg = np.zeros_like(X[:, 0])
            S_ff_avg = np.zeros_like(F[:, 0])
        elif estimator == 'H2':
            S_xx_avg = np.zeros_like(X[:, 0])
            S_xf_avg = np.zeros_like(F[:, 0])
        else:
            S_fx_avg, S_ff_avg, S_xx_avg, S_xf_avg = None, None, None, None
            raise Exception('Invalid estimator. Enter H1 or H2.')
        for i in range(N):
            if estimator == 'H1':
                if filter_list is not None:
                    if i not in filter_list:
                        S_fx_avg += np.conj(F[:, i]) * X[:, i]
                        S_ff_avg += np.conj(F[:, i]) * F[:, i]
                else:
                    S_fx_avg += np.conj(F[:, i]) * X[:, i]
                    S_ff_avg += np.conj(F[:, i]) * F[:, i]
            elif estimator == 'H2':
                if filter_list is not None:
                    if i not in filter_list:
                        S_xx_avg += np.conj(X[:, i]) * X[:, i]
                        S_xf_avg += np.conj(X[:, i]) * F[:, i]
                else:
                    S_xx_avg += np.conj(X[:, i]) * X[:, i]
                    S_xf_avg += np.conj(X[:, i]) * F[:, i]
            else:
                print('Invalid estimator')
                return
        if estimator == 'H1':
            if kind == 'admittance':
                return S_fx_avg / S_ff_avg
            elif kind == 'impedance':
                return S_ff_avg / S_fx_avg
            else:
                print('Invalid FRF type')
                return
        elif estimator == 'H2':
            if kind == 'admittance':
                return S_xx_avg / S_xf_avg
            elif kind == 'impedance':
                return S_xf_avg / S_xx_avg
            else:
                print('Invalid FRF type')
                return

    @staticmethod
    def load_from_json(path):
        with open(path, 'r') as f:
            dict_ = json.load(f)
        return dict_

    def save_to_json(self, path):
        with open(path, 'w') as f:
            json.dump(self.dof_data, f)

    def plot_op_meas(self):
        fig = plt.figure(figsize=(15, 2.2))
        ax = fig.add_axes([0.1, 0.1, .8, .8])
        ax.plot(np.linspace(0, self.acq.acquisition_time, self.acq.acquisition_time*self.acq.sampling_rate),
                self.measurement_array.T)
        ax.set_xlabel('time [s]')
        ax.grid()
        fig.patch.set_facecolor('#cafac5')
        plt.show()


    # TODO: Operational measurement methods
    #def start_op_measurement(self, acq_time=None, save_to=None, start_w_button=True):
    #    # acq_time omejen na celo število
    #    if acq_time is not None:
    #        self.acq.acquisition_time = acq_time
    #    self.measurement_array, pbar = None, None
    #    if start_w_button:
    #        start_meas_button = widgets.Button(description='Start measurement')

    #        display(start_meas_button)

    #        def start_btn_clicked(B):
    #            clear_output()
    #            print('Start btn pressed')
    #            global pbar
    #            pbar = self.acquire_op_signal(save_to=save_to)

    #        start_meas_button.on_click(start_btn_clicked)

    #    else:
    #        pbar = self.acquire_op_signal(save_to=save_to)

    #def acquire_op_signal(self, save_to):
    #    self.measurement_array = np.zeros((len(self.all_channels),
    #                                       int(self.acq.sampling_rate * self.acq.acquisition_time)),
    #                                      dtype=np.float64)
    #    try:
    #        pbar = tqdm(total=self.acq.acquisition_time)
    #        i = 1
    #        if self.data_source=='NI':
    #            self.task.start()
    #        if self.data_source=='Dewesoft':
    #            self.hllDll.dsconStartMeasurement(self.conn_instance)
    #        # TODO: Dodaj meritve z DEWESOFTOM !!
    #        start_time = time.time()
    #        
    #        while True:
    #            self.measurement_array[:, (i - 1) * self.acq.sampling_rate:i * self.acq.sampling_rate] = np.array(
    #                self.task.read(number_of_samples_per_channel=self.acq.sampling_rate, timeout=10.0))
    #            pbar.update()
    #            if math.floor(time.time() - start_time) >= self.acq.acquisition_time:
    #                pbar.container.children[-2].style.bar_color = 'green'
    #                break
    #            i += 1
    #        self.task.stop()
    #        self.plot_op_meas()
    #        self.save_op_test_results(save_to, pbar)
    #    except nidaqmx.DaqError:
    #        clear_output()
    #        self.task.stop()
    #        self.acquire_op_signal(save_to=save_to)
    #    return pbar


    #def save_op_test_results(self, save_to, pbar):
    #    out = Output()
    #    # Save measurement info
    #    save_meas_info_choice = widgets.ToggleButtons(
    #        options=['No', 'Yes'],
    #        description='Save measurement info: \n',
    #        disabled=False,
    #        button_style='',  # 'success', 'info', 'warning', 'danger' or ''
    #        style={'description_width': 'initial'}
    #    )
    #    # Save self.measurements_temp
    #    save_button = widgets.Button(description='Save')
    #    # Buttons for measurement series
    #
    #    if save_to is None:
    #        file_name = widgets.Text(description='Save to: ',
    #                                 placeholder='Filename',
    #                                 value='')
    #        widgets_ = [save_button, save_meas_info_choice, file_name]
    #    else:
    #        widgets_ = save_button, save_meas_info_choice
    #    # widgets layout
    #    grid = GridspecLayout(2, 2)
    #    grid[0, 0] = widgets_[0]
    #    grid[1, :] = widgets_[1]
    #    if save_to is None:
    #        grid[0, 1:] = widgets_[2]
    #    display(grid)
    #
    #    def save_btn_clicked(B, save_to_=save_to):
    #        if save_to_ is None:
    #            save_to_ = str(file_name.value)
    #            if len(save_to_) == 0:
    #                message = 'Enter file name!'
    #            else:
    #                message = f'Measurement saved to \"{save_to_}.npy\"'
    #                np.save(f'{save_to_}.npy', self.measurement_array.squeeze())
    #                if save_meas_info_choice.value == 'Yes':
    #                    message += f'\nMeasurement info saved to \"{save_to_}.json\"'
    #                    json_obj = json.dumps(self.meas_info, indent=4)
    #                    with open(f'{save_to_}.json', 'w') as meas_data_file:
    #                        meas_data_file.write(json_obj)
    #                pbar.container.children[-2].style.bar_color = 'black'
    #        else:
    #            np.save(f'{save_to_}.npy', self.measurement_array.squeeze())
    #            message = f'Measurements saved to \"{save_to_}.npy\"'
    #            if save_meas_info_choice.value == 'Yes':
    #                message += f'\nMeasurement info saved to \"{save_to_}.json\"'
    #                json_obj = json.dumps(self.meas_info, indent=4)
    #                with open(f'{save_to_}.json', 'w') as meas_data_file:
    #                    meas_data_file.write(json_obj)
    #            pbar.container.children[-2].style.bar_color = 'black'
    #        with out:
    #            clear_output()
    #            print(message)
    #        display(out)
    #
    #    save_button.on_click(save_btn_clicked)
