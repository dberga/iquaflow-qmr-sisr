# IQUAFLOW - Quality Metrics for Single Image Super Resolution

Note: Use any of our [jupyter notebooks](https://github.com/dberga/iquaflow-qmr-sisr/blob/master/IQF-UseCase.ipynb) to run the use case.

- The rest of code is distributed in distinct repos [IQUAFLOW framework](https://github.com/satellogic/iquaflow), [QMRNet EO Dataset Evaluation Use Case](https://github.com/dberga/iquaflow-qmr-eo) and [QMRNet's Loss for SR](https://github.com/dberga/iquaflow-qmr-loss).

# SISR Algorithms 

The Single Image Super Resolution (SISR) use case is build to compare the image quality between different SiSR solutions. A SiSR algorithm inputs one frame and outputs an image with greater resolution.
These are the methods that are being compared in the use case:

1. Fast Super-Resolution Convolutional Neural Network (FSRCNN) [Ledig et al., 2016]
2. Single Image Super-Resolution Generative Adversarial Networks (SRGAN) [Dong et al., 2016]
3. Multi-scale Residual Network (MSRN) [Li et al., 2018]
4. Enhanced Super-Resolution Generative Adversarial Networks (ESRGAN) [Wang et al., 2018]
5. Content Adaptive Resampler (CAR) [Sun & Chen, 2019]
6. Local Implicit Image Function (LIIF) [Chen et al., 2021]

A use case in IQF usally involves wrapping a training within mlflow framework. In this case we estimate quality on the solutions offered by the different Dataset Modifiers which are the SISR algorithms. Similarity metrics against the Ground Truth are then compared.

____________________________________________________________________________________________________


## To reproduce the experiments:

1. `git clone https://YOUR_GIT_TOKEN@github.com/dberga/iquaflow-qmr-sisr.git`
2. `cd iquaflow-qmr-sisr`
3. Then build the docker image with `make build`.(\*\*\*) This will also download required datasets and weights.
4. In order to execute the experiments:
    - `make dockershell` (\*)
    - Inside the docker terminal execute `python ./IQF-UseCase.py`
5. Start the mlflow server by doing `make mlflow` (\*)
6. Notebook examples can be launched and executed by `make notebookshell NB_PORT=[your_port]"` (\**)
7. To access the notebook from your browser in your local machine you can do:
    - If the executions are launched in a server, make a tunnel from your local machine. `ssh -N -f -L localhost:[your_port]:localhost:[your_port] [remote_user]@[remote_ip]`  Otherwise skip this step.
    - Then, in your browser, access: `localhost:[your_port]/?token=sisr`


____________________________________________________________________________________________________

## Notes

   - The results of the IQF experiment can be seen in the MLflow user interface.
   - For more information please check the IQF_expriment.ipynb or IQF_experiment.py.
   - There are also examples of dataset Sanity check and Stats in SateAirportsStats.ipynb
   - The default ports are `8888` for the notebookshell, `5000` for the mlflow and `9197` for the dockershell
   - (*)
        Additional optional arguments can be added. The dataset location is:
        >`DS_VOLUME=[path_to_your_dataset]`
   - To change the default port for the mlflow service:
     >`MLF_PORT=[your_port]`
   - (**)
        To change the default port for the notebook: 
        >`NB_PORT=[your_port]`
   - A terminal can also be launched by `make dockershell` with optional arguments such as (*)
   - (***)
        Depending on the version of your cuda drivers and your hardware you might need to change the version of pytorch which is in the Dockerfile where it says:
        >`pip3 install torch==1.7.0+cu110 torchvision==0.8.1+cu110 -f https://download.pytorch.org/whl/torch_stable.html`.
   - (***)
        The dataset is downloaded with all the results of executing the dataset modifiers already generated. This allows the user to freely skip the `.execute` as well as the `apply_metric_per_run` which __take long time__. Optionally, you can remove the pre-executed records folder (`./mlruns `) for a fresh start.
        
Note: make sure to replace "YOUR_GIT_TOKEN" to your github access token, also in [Dockerfile](https://github.com/dberga/iquaflow-qmr-eo/blob/master/Dockerfile).

# Cite

If you use content of this repo, please cite:

```
@article{berga2022,
  title={QMRNet: Quality Metric Regression for EO Image Quality Assessment and Super-Resolution},
  author={Berga, David and Gallés, Pau and Takáts, Katalin and Mohedano, Eva and Riordan-Chen, Laura and Garcia-Moll, Clara and Vilaseca, David and Marín, Javier},
  journal={arXiv preprint arXiv:2210.06618},
  year={2022}
}
@article{galles2022,
  title={IQUAFLOW: A NEW FRAMEWORK TO MEASURE IMAGE QUALITY},
  author={Gallés, Pau and Takáts, Katalin and Hernández-Cabronero, Miguel and Berga, David and Pega, Luciano and Riordan-Chen, Laura and Garcia-Moll, Clara and Becker, Guillermo and Garriga, Adán and Bukva, Anica and Serra-Sagristà, Joan and Vilaseca, David and Marín, Javier},
  journal={arXiv preprint arXiv:XXXX.XXXXX},
  year={2022}
}
```
