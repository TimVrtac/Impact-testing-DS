import nidaqmx
# math functions
import numpy as np
# data manipulation
import pandas as pd
# trigger
from pyTrigger import pyTrigger

class NISetup:
    def __init__(self, acquisition_time, sampling_rate=None, samps_per_chn=None,
                 task_name=None, sensor_xlsx=None, sensor_list=None, 
                 no_impacts=None,
                 trigger_type='up', trigger_level=10.0, presamples=100, imp_force_lim=0.015, double_imp_force_lim=1,
                 terminal_config=nidaqmx.constants.TerminalConfiguration.PSEUDO_DIFF,
                 excitation_source=nidaqmx.constants.ExcitationSource.INTERNAL,
                 current_excit_val=0.004, sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS):
        """
        # TODO: Trenutno samo za IEPE
        # TODO: Check for double impacts -> prilagodi beepe
        # TODO: Force okno
        # TODO: Kontinuirana meritev
        # TODO: Preveri imena naprav v primeru ene same kartice
        nidaqmx constants: https://nidaqmx-python.readthedocs.io/en/latest/constants.html

        # Sensor data parameters
        :param sensor_xlsx: path to the Excel file with sensor data
        :param sensor_list: list of sensors (Serial numbers) or dict of shape {SN: [list of directions (x,y,z)]}

        # General channel configuration parameters
        :param terminal_config: terminal configuration parameter (DEFAULT, DIFF, NRSE,
                                PSEUDO_DIFF, RSE - see nidaqmx constants)
        :param excitation_source: excitation source parameter (EXTERNAL, INTERNAL, NONE - see nidaqmx constants)
        :param current_excit_val: excitation current [A] (float)

        # Sampling parameters
        :param sample_mode: sampling mode (CONTINUOUS, FINITE, HW_TIMED_SINGLE_POINT - see nidaqmx constants)
        :param sampling_rate: sampling rate [Hz] (int)
        :param samps_per_chn: Specifies the number of samples to acquire or generate for each channel in the task if
                              **sample_mode** is **FINITE_SAMPLES**. If **sample_mode** is **CONTINUOUS_SAMPLES**,
                               NI-DAQmx uses this value to determine the buffer size.
        :param acquisition_time: acquisition time [s] (int/float)

        # Trigger configuration parameters
        :param trigger_type: trigger type (up, down or abs - string)
        :param trigger_level: the level to cross, to start trigger (float)
        :param presamples # of presamples

        # Double impact control
        :param imp_force_lim: Limit  value of force derivative for determination of start/end point of the impact
        """
        # ACQUISITION SYSTEM
        self.acq_name = 'NI'

        # ACQUISITION PARAMETERS
        self.acquisition_time = acquisition_time
        self.sampling_rate = sampling_rate
        self.samples_per_channel = int(self.sampling_rate * self.acquisition_time)

        # Sensor data DataFrame
        self.sensor_df = pd.read_excel(sensor_xlsx)
        self.sensor_list = sensor_list
        self.sensor_dict = {}

        # SETUP NI TASK
        # Get all connected NI devices
        system = nidaqmx.system.System.local()
        self.device_list = [_.name for _ in list(system.devices)]

        # Open new task
        try:
            self.task = nidaqmx.task.Task(new_task_name=task_name)
        except nidaqmx.DaqError:
            new_task_name = False
            i = 1
            while not new_task_name:
                try:
                    self.task = nidaqmx.task.Task(new_task_name=task_name + '_{i}')
                    new_task_name = True
                except nidaqmx.DaqError:
                    i += 1
                if i > 5:
                    print('To many tasks generated. Restart kernel to generate new tasks.')
                    break
            print(f"Repeated task name: task name changed to {task_name + '_'}")
        self.excitation_source = excitation_source
        self.current_excit_val = current_excit_val

        # General channel parameters
        self.terminal_config = terminal_config
        # nidaqmx constants - unit conversion
        self.unit_conv = {'mV/g': nidaqmx.constants.AccelSensitivityUnits.MILLIVOLTS_PER_G, #'mV/m/s**2': constants.AccelSensitivityUnits.MILLIVOLTS_PER_G,-> mV/m/s**2 ne obstaja -> pretvorba občutljivosti v mV/m/g!
                        'g': nidaqmx.constants.AccelUnits.G,
                        'm/s**2': nidaqmx.constants.AccelUnits.METERS_PER_SECOND_SQUARED,
                        'mV/N': nidaqmx.constants.ForceIEPESensorSensitivityUnits.MILLIVOLTS_PER_NEWTON,
                        'N': nidaqmx.constants.ForceUnits.NEWTONS}

        # add channels to the task
        self.chn_names = []
        self.add_channels()

        # sampling configuration
        self.task.timing.cfg_samp_clk_timing(rate=self.sampling_rate, sample_mode=sample_mode,
                                            samps_per_chan=samps_per_chn)  # set sampling for the task

        # list all channels
        self.all_channels = [str(_.name) for _ in self.task.ai_channels]

        try:
            self.force_chn_ind = int(np.where(np.array(self.all_channels) == 'force')[0])
        except TypeError:
            print('No force sensor.')

        # TRIGGER CONFIGURATION
        self.trigger_type = trigger_type
        self.trigger_level = trigger_level
        self.presamples = presamples

        

    # Task generation methods
    def add_channels(self):
        """
        sensors: list of sensors (Serial numbers) or dict of shape {SN: [list of directions ('x','y','z')]}
        task: nidaqmx Task instance
        df: dataframe with sensor data
        """

        device_ind = 1  # pričakovan cDAQ5Mod1
        dev_chn_ind = 0
        sensor_ind = 0

        if type(self.sensor_list) == list:
            for i in self.sensor_list:
                temp_df_ = self.sensor_df[self.sensor_df['SN'].astype(str) == i]
                if temp_df_.empty:
                    raise ValueError(f'Invalid serial number: {i}. Check if the given SN is correct and that it is '
                                     f'included in measurement data file (Merilna oprema.xlsx)')
                for _, chn_ in temp_df_.iterrows():
                    # channel selection
                    try:
                        phys_chn = self.device_list[device_ind] + f'/ai{dev_chn_ind}'
                        chn_name = self.get_chn_name(chn_, sensor_ind)
                        self.new_channel(chn_, physical_channel=phys_chn, name_to_assign_to_channel=chn_name,
                                         min_val=chn_.Min, max_val=chn_.Max,
                                         units=self.unit_conv[chn_['Izhodna enota']],
                                         sensitivity=chn_.Obcutljivost,
                                         sensitivity_units=self.unit_conv[chn_['Enota obcutljivosti']])
                        dev_chn_ind += 1
                    except nidaqmx.DaqError:
                        device_ind += 1
                        dev_chn_ind = 0
                        phys_chn = self.device_list[device_ind] + f'/ai{dev_chn_ind}'
                        chn_name = self.get_chn_name(chn_, sensor_ind)
                        self.new_channel(chn_, physical_channel=phys_chn, name_to_assign_to_channel=chn_name,
                                         min_val=chn_.Min, max_val=chn_.Max,
                                         units=self.unit_conv[chn_['Izhodna enota']],
                                         sensitivity=chn_.Obcutljivost,
                                         sensitivity_units=self.unit_conv[chn_['Enota obcutljivosti']])
                        dev_chn_ind += 1
                    self.chn_names.append(chn_name)
                    self.sensor_dict[dev_chn_ind-1] = {'Name': chn_name, 'Sensitivity': chn_.Obcutljivost, 'RangeMinValue': chn_.Min, 'RangeMaxValue': chn_.Max}
                sensor_ind += 1

        elif type(self.sensor_list) == dict:
            for sensor_, dir_ in self.sensor_list.items():
                # selecting channels from sensor_df
                temp_df_ = self.sensor_df['SN'].astype(str) == sensor_
                if (temp_df_ == False).all():
                    raise ValueError(f'Invalid serial number: {sensor_}. Check if the given SN is correct and that it '
                                     f'is included in measurement data file (Merilna oprema.xlsx)')
                df_mask = np.zeros_like(temp_df_)
                for i in dir_:
                    df_mask = df_mask | (self.sensor_df['Smer'].astype(str) == i)
                temp_df_ = self.sensor_df[temp_df_ & df_mask]

                for _, chn_ in temp_df_.iterrows():
                    # channel selection
                    try:
                        phys_chn = self.device_list[device_ind] + f'/ai{dev_chn_ind}'
                        chn_name = self.get_chn_name(chn_, sensor_ind)
                        print(chn_name)
                        self.new_channel(chn_, physical_channel=phys_chn, name_to_assign_to_channel=chn_name,
                                         min_val=chn_.Min, max_val=chn_.Max,
                                         units=self.unit_conv[chn_['Izhodna enota']],
                                         sensitivity=chn_.Obcutljivost,
                                         sensitivity_units=self.unit_conv[chn_['Enota obcutljivosti']])
                        # print(sensor, phys_chn, chn_name)
                        dev_chn_ind += 1
                    except nidaqmx.DaqError:
                        device_ind += 1
                        dev_chn_ind = 0
                        phys_chn = self.device_list[device_ind] + f'/ai{dev_chn_ind}'
                        chn_name = self.get_chn_name(chn_, sensor_ind)
                        print(chn_name)
                        self.new_channel(chn_, physical_channel=phys_chn, name_to_assign_to_channel=chn_name,
                                         min_val=chn_.Min, max_val=chn_.Max,
                                         units=self.unit_conv[chn_['Izhodna enota']],
                                         sensitivity=chn_.Obcutljivost,
                                         sensitivity_units=self.unit_conv[chn_['Enota obcutljivosti']])
                        # print( sensor_, phys_chn, chn_name)
                        dev_chn_ind += 1
                    sensor_ind += 1

    def new_channel(self, chn_data, physical_channel, name_to_assign_to_channel, min_val, max_val, units,
                    sensitivity, sensitivity_units):
        # Function adds new channel to the task
        if chn_data['Merjena veličina'] == 'sila':
            self.task.ai_channels.add_ai_force_iepe_chan(physical_channel, name_to_assign_to_channel,
                                                         self.terminal_config,
                                                         min_val, max_val, units, sensitivity, sensitivity_units,
                                                         current_excit_source=self.excitation_source,
                                                         current_excit_val=self.current_excit_val,
                                                         custom_scale_name='')
        else:
            self.task.ai_channels.add_ai_accel_chan(physical_channel, name_to_assign_to_channel, self.terminal_config,
                                                    min_val, max_val, units, sensitivity, sensitivity_units,
                                                    current_excit_source=self.excitation_source,
                                                    current_excit_val=self.current_excit_val,
                                                    custom_scale_name='')

    @staticmethod
    def get_chn_name(chn_, ind_):
        # Function generates channel name string.
        if chn_['Merjena veličina'] == 'sila':
            return 'force'
        else:
            return f'{ind_}{chn_.Smer}'

    def get_impact(self, imp=None):
        """
        imp parameter is not used in this method (needed for measurements using dewesoft).
        Adopted from Impact testing v1.
        :return: measured data - individual measurement
        """
        trigger = pyTrigger(rows=self.samples_per_channel, channels=len(self.all_channels),
                            trigger_type=self.trigger_type,
                            trigger_channel=self.force_chn_ind,
                            trigger_level=self.trigger_level,
                            presamples=self.presamples)

        trig = True
        self.task.start()
        while True:
            data = self.measure_NI()
            trigger.add_data(data.T)
            if trigger.finished:
                self.task.stop()
                break
            if trigger.triggered == True and trig == True:
                trig = False
            
        return trigger.get_data().T

    def measure_NI(self):
        data = np.array(self.task.read(number_of_samples_per_channel=self.samples_per_channel,
                                       timeout=10.0))
        return data