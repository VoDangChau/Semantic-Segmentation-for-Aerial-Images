# Semantic-Segmentation-for-Aerial-Images

In this project, we investigate the problem of Semantic Segmentation for agricultural aerial imagery. This is due to the fact that methods normally applied for semantic segmentation are designed without considering two characteristics of  the aerial data: (i) 
the top-down perspective implies that images lack depth; (ii) there can be a strong  imbalance in the distribution of semantic classes because 
the relevant objects of the scene may appear at extremely different scales (for example, an object only account for 10% of the photo while the other 90% is background).
We propose a solution to these problems based on two ideas: (1) we use together a set of suitable augmentation and a 
consistency loss to guide the model to learn semantic representations that are invariant to the photometric and geometric 
shifts typical of the top-down perspective (Augmentation Invariance); (2) we use a sampling method (Adaptive Sampling)
that select the training images based on a measure of pixel-wise distribution of classes and actual network confidence. 

## Pipeline
![image](https://user-images.githubusercontent.com/91112707/230101003-8be140f2-b597-4a08-938d-594b55662686.png)

## Dataset
We use Dataset from a competition called AGRICULTURE-VISION. They are aerial images with top-down perspective.
![image](https://user-images.githubusercontent.com/91112707/230102990-786ec7c1-a0cb-4aff-ab52-7d00c9d2e269.png)


## Result
The result of some models and our proposed method applied for the task.
![image](https://user-images.githubusercontent.com/91112707/230098430-de3d54a5-25f2-4d27-9fac-c27603daa4ad.png)

The result achieves highest performance when we apply 30 degree rotation instead of 90 degree rotation for Augmentation Invariance method and Focal loss instead of Cross Entropy.
