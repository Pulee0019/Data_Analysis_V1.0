# 1 Environment Installation
## 1.1 Environment Create and Activate
```
conda create -n data_analysis python=3.10 -y
conda activate data_analysis
```
## 1.2 Installation
```
pip install numpy
pip install pandas
pip install matplotlib
pip install opencv-python
pip install spicy
pip install scikit-learn
```
# 2 How to run fiber-running analysis?
###  You can run Main_analysis.py to start-up analysis UI
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
> This function will auto detect the optogenetics sessions and its' parameters exclude power, so you need enter the power of corresponding session.
>
![optogenetics configuration](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/optogenetics%20configuration.png)
## 3.2 Data import
![data import](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/data%20import.png)
### 3.2.1 Single import
> Single import requires the corresponding file format.
> 
### 3.2.2 Multi import
> Multi import requires the corresponding file format.
>
## 3.3 Analysis
> Include Running Data Analysis, Fiber Data Preprocessing, Fiber Data Analysis and Behaviour Analysis (Only activate in full analysis).
> 
![analysis](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/anlysis.png)
### 3.3.1 Running analysis
> You can change the parameter (smooth method, threshold) to detect running bout and preview the detected bouts in window.
> 
![running analysis1](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20analysis1.png)
![running analysis2](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20analysis2.png)
![running analysis3](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20analysis3.png)
### 3.3.2 Fiber data preprocessing
> In this window, you can select target signal (signal combination except 410 nm), reference single (410/baseline), apply smooth (Savitzky-Golay filter), baseline correction (include polynomial and exponential fitting) and motion correction.
>
![fiber preprocess](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/fiber%20preprocess.png)
![fiber preprocess1](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/fiber%20preprocess1.png)
![fiber preprocess2](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/fiber%20preprocess2.png)
![fiber preprocess4](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/fiber%20preprocess4.png)
### 3.3.3 Fiber data analysis
> In this window, you can calculate total ΔF/F and Z-score.
>
## 3.4 Multimodal analysis
> Include Running-Induced Activity Analysis, Drug-Induced Activity Analysis, Optogenetic-Induced Activity Analysis.
>
![multimodal analysis](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/multimodal%20analysis.png) 
### 3.4.1 Running-Induced Activity Analysis
> Include Running, Running + Drug, Running + Optogentics and Running + Optogenetics + Drug. Running is used for you only record the fiber photometry and running speed. Running + Drug is used when you administrate drug (chemical genetics/pharmacology) and record the data as Running described. Running + Optogentics is used when you deliver optogenetic stimulation(s) and record the data as above described. Running + Optogenetics + Drug is used when you administrate drug, deliver optogenetic stimulation(s) and record the data as above described.
> 
![running induced](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20induced.png)
> Click the anyone of menus as above described, the window of animals assignment and parameter setting will pop up.
>
![running induced1](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/running%20induced1.png)
### 3.4.2 Drug-Induced Activity Analysis
>  Click the menu, the window of drug administration sessions assignment and parameter setting will pop up.
> 
![drug induced](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/drug%20induced.png)
### 3.4.3 Optogenetics-Induced Activity Analysis
>  Include Optogenetics and Optogenetics + Drug. Optogentics is used when you deliver optogenetic stimulation(s) and record the data as above described. Optogenetics + Drug is used when you administrate drug, deliver optogenetic stimulation(s) and record the data as above described.
> 
![optogenetics induced](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/optogenetics%20induced.png)
> Click the menu, the window of optogenetic sessions assignment and parameter setting will pop up.
>  
![optogenetics induced1](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/optogenetics%20induced1.png)