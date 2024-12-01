import os


def batch_rename_images(folder_path, new_prefix):

    file_list = os.listdir(folder_path)


    for file_name in file_list:

        old_path = os.path.join(folder_path, file_name)
        new_name = new_prefix + file_name
        new_path = os.path.join(folder_path, new_name)


        os.rename(old_path, new_path)



folder_path = './image/'
new_prefix = 'COCO_train2014_'
batch_rename_images(folder_path, new_prefix)