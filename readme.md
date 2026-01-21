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
# 3.1 Setting
> You can select experiment type, configure event label, configure drug name and configure optogenetics power in setting.
> 
### 3.1.1 Experiment Type
> Include running only and full analysis, running only need the fiber photometry data and ast2 data, full analysis need the running only needed data and deeplabcut behaviour tracking data.
> 
![experiment type](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/experiment%20type.png)
### 3.1.2 Event Configuration
> You can 
>
![event configuration](https://github.com/Pulee0019/Data_Analysis_V1.0/blob/main/imgs/event%20configuration.png)
### 3.1.3 