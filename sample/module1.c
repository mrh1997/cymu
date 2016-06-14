int a, b = 10, c;

void set_a_to(int new_value);

void demo_func()
{
	set_a_to(3);
	if (a)
	{
		int local_var = 10;
		while (local_var -= 1)
		{
			b -= 1;
			a -= 1;
		}
	}
	else
		c = 3;
}

void set_a_to(int new_value)
{
	a = new_value;
	return;
}
