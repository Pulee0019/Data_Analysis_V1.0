# 1 Environment Installation
## 1.1 Environment Create and Activate
```
conda create -n data_analysis python=3.10 -y
conda activate data_analysis
```
## 1.2 Installation
```
pip install -r requirements.txt
```
# 2 How to run fiber-treadmill analysis (FTA)?
###  You can run main.py to start-up analysis UI
- To start the app, run `python main.py` in this directory.
- If startup fails due to missing packages, run `pip install -r requirements.txt`.

## 2.1 Project Structure
```
FTA/
  main.py
  analysis_core/
    Behavior_analysis.py
    Fiber_analysis.py
    Running_analysis.py
  analysis_multimodal/
    Multimodal_analysis.py
    Running_induced_activity_analysis.py
    Drug_induced_activity_analysis.py
    Optogenetic_induced_activity_analysis.py
  infrastructure/
    logger.py
  core/
    config_store.py
    io.py
    analysis_results.py
  workflows/
    data_workflows.py
    analysis_workflows.py
  ui/
    bodypart_controller.py
    view_controller.py
    settings_dialogs.py
    windows/
      visualization_windows.py
  config/
    event_config.json
    opto_power_config.json
    drug_name_config.json
  memory/
    channel_memory.json
```
# 3 The introduction of analysis UI
## 3.1 Setting
> You can select experiment type, configure event label, configure drug name and configure optogenetics power in setting.
> 
### 3.1.1 Experiment Type
> Include running only and full analysis, running only need the fiber photometry data and ast2 data, full analysis need the running only needed data and deeplabcut behaviour tracking data.
> 
![experiment type](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/experiment%20type.png)
### 3.1.2 Event Configuration
> You can configure the event name include drug, running start and optogenetics. Specially, if you have multi-drug events, you can enter multi-drug-event names, space by ", ".
>
![event configuration](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/event%20configuration.png)
### 3.1.3 Optogenetic configuration
> This function will automatically detect the optogenetics sessions and its' parameters exclude power, so you need enter the power of corresponding session after importing data.
>
![optogenetics configuration](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/optogenetics%20configuration.png)
### 3.1.4 Drug configuration
> This function will automatically detect the drug sessions, admininstration time and offset time according the event configuration. You can configure the drug name if you need and enter the onset time to exclude the running or other events affected by drug induced trace shift.
>
![drug configuration](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/drug%20configuration.png)
## 3.2 Data import
![data import](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/data%20import.png)
### 3.2.1 Single import
> Single import requires the following file format. Select the folder ```..``` can import single animal data.
```
Typical directory structure:
../
  filename_AST2_1.ast2
  Experiment/
    2026_04_10-16_50_12/
      Events.csv
      Fluorescence.csv
      Fluorescence-unaligned.csv
      Outputs.csv
```
### 3.2.2 Multi import
> Multi import requires the following file format. Selcct the folder ```..``` can import multi animal data.
```
Typical directory structure:
../
  20260410/
    202604101/
      2839_2839_2838_2838/
        filename_AST2_1.ast2
        Experiment/
          2026_04_10-16_50_12/
            Events.csv
            Fluorescence.csv
            Fluorescence-unaligned.csv
            Outputs.csv
```
## 3.3 Analysis
> Include Running Data Analysis, Fiber Data Preprocessing, Fiber Data Analysis and Behaviour Analysis (Only activate in full analysis).
> 
![analysis](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/anlysis.png)
### 3.3.1 Running analysis
> You can change the parameter (smooth method[figure3.3.1.2](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20analysis2.png), bouts type[figure3.3.1.3](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20analysis.png), bouts direction[figure3.3.1.4](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20analysis4.png) and threshold for bout detection) to detect running bout and preview the detected bouts in window.

#### The defination of different **bout types**:
##### **General bout** is defined by the speed exceed the **general threshold** for at least **genral min duration**.
##### **Locomotion bout** is the general bout meet the two additional criteria, firstly, the mean absolute speed during the **pre-locomotion buffer** and the **post-locomotion buffer** remain below the **general threshold**, secondly, the duration of the bout exceed **locomotion duration**.
##### **Jerk bout** is the general bout meet the **fisrt criteria of locomotion bout** but the second criteria is the duration of the bout below **locomotion duration**. 
##### **Reset bout** is the general bout when the mean absolute speed during **post-locomotion buffer** exceed the **general threshold**.
##### **Other bout** is the general bout but not locomotion, jerk and reset bout.
##### **Rest bout** is defined by the speed below the **general threshold** for at least **min rest duration**.
#### The defination of different **bout directions**:
##### **General** is the bout type without direction classification. The ratio between bout mean speed and bout mean absolute speed higher than **move direction threshold** called **Forward**, lower than the **negative move direction threshold** called **Backward**, lower than **move direction threshold** but higer than **negative move direction threshold** called **balance**.

> 
![running analysis1](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20analysis1.png)
![running analysis2](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20analysis2.png)
![running analysis3](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20analysis3.png)
![running analysis4](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20analysis4.png)
### 3.3.2 Fiber data preprocessing
> In this window, you can select target signal (signal combination except 410 nm)[figure3.2.2.2](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/fiber%20preprocess2.png), reference single (410/baseline)[figure3.2.2.3](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/fiber%20preprocess3.png), apply smooth (Savitzky-Golay filter), baseline correction (include polynomial and exponential fitting)[figure3.2.2.4](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/fiber%20preprocess4.png) and motion correction.

#### **Smooth** is used to reduce the noise collected by device, if you want to analysis the variance of phase or frequency, we aren't recommand smooth the signal.
#### **Baseline correction** is used to reduce the fiber autofluorescence induced photobleaching. If you select **polynomial**, the target signal and reference signal will fitted used 21st-degree polynomial curve, and then substract it, recommand it for the analysis **except drug-induced activity analysis**. If you select **exponential**, the trace will fitted used the exponential function post drug administration and extrapolated to correct the entire post drug period, then substract the fitted curve, recommand it during **drug-induced activity analysis, long time scale optogenetic but short recording optogenetic-induced activity analysis without drug admininstration, long enforced running but short recording running-induced acitivity analysis**.
#### **Motion correction** is used to reduced the motion induced artifacts. If baseline-corrected, the baseline-corrected reference signal was fitted to the baseline-corrected target signal using least squares linear regression to estimate the motion-related component, if not baseline-correction, the fitted reference signal if 410 else median reference signal was used as motion-related component, then substrated the component, called ΔF.
>
![fiber preprocess1](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/fiber%20preprocess1.png)
![fiber preprocess2](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/fiber%20preprocess2.png)
![fiber preprocess3](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/fiber%20preprocess3.png)
![fiber preprocess4](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/fiber%20preprocess4.png)
### 3.3.3 Fiber data analysis
> In this window, you can calculate overall ΔF/F and Z-score.
#### The calculation of ΔF/F (ΔF/F0， ΔF is described above):
##### The control is 410 with baseline-correction, F0 is median of full-time raw target signal.
##### The control is 410 without baseline-correction, F0 is the motion fitted 410.
##### The control is baseline, with/without baseline-correction, F0 is the median of baseline.
#### The calculation of Z-score:
##### For overall Z-score, it is calculate as the overall ΔF/F substract the mean of overall ΔF/F, and then be divided by the standard deviation of overall ΔF/F.
##### For event-related Z-score, it is calculate as the event cropped ΔF/F substract the post mean of cropped ΔF/F, and then be divided by the post standard deviation of cropped ΔF/F.
>
## 3.4 Multimodal analysis
> Include Running-Induced Activity Analysis, Drug-Induced Activity Analysis, Optogenetic-Induced Activity Analysis.
>
![multimodal analysis](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/multimodal%20analysis.png) 
### 3.4.1 Running-Induced Activity Analysis
> Include Running, Running + Drug, Running + Optogentics and Running + Optogenetics + Drug. Running is used for you only record the fiber photometry and running speed. Running + Drug is used when you administrate drug (chemical genetics/pharmacology) and record the data as Running described. Running + Optogentics is used when you deliver optogenetic stimulation(s) and record the data as above described. Running + Optogenetics + Drug is used when you administrate drug, deliver optogenetic stimulation(s) and record the data as above described.
> 
![running induced1](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20induced1.png)
> Click the anyone of menus as above described, the window of animals assignment and parameter setting will pop up.
>
![running induced2](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20induced2.png)
### 3.4.2 Drug-Induced Activity Analysis
>  Click the menu, the window of drug administration sessions assignment and parameter setting will pop up.
> 
![drug induced](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/drug%20induced.png)
### 3.4.3 Optogenetics-Induced Activity Analysis
>  Include Optogenetics and Optogenetics + Drug. Optogentics is used when you deliver optogenetic stimulation(s) and record the data as above described. Optogenetics + Drug is used when you administrate drug, deliver optogenetic stimulation(s) and record the data as above described.
> 
![optogenetics induced1](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/optogenetics%20induced1.png)
> Click the menu, the window of optogenetic sessions assignment and parameter setting will pop up.
>  
![optogenetics induced2](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/optogenetics%20induced2.png)
### 3.4.4 Bout Analysis
> Inlude Running and Running+Drug. Running is used when compare different days/drug admininstration in different recordings. Running+Drug is used when compare drug effect on running in single recordings.

> Different from multimodal analysis described above, the plot window can enter a string (such as start, end, start+1000, end-1000), to acquire same window length for the bout statistic of duration, peak and mean. Also for the histgram disturbution of bout speed.

![bout analysis1](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/bout%20analysis1.png)
> Click the menu, the window of animal assignment and parameter setting will pop up.

![bout analysis2](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/bout%20analysis2.png)