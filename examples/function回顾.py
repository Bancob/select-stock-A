def hello(param):
    print('hello', param)


hello('西蒙斯')


# exit()


def hello_pro(*args):
    print('hello pro', args)
    print('hello pro', *args)


hello_pro('西蒙斯', '邢不行')


def hello_max(*args, **kwargs):
    print('hello max', *args)
    print('hello max其他参数', kwargs)


hello_max('西蒙斯', '邢不行', '马科维茨', ta=1, simons=2)
